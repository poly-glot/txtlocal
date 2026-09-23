import asyncio
import csv
import io
import re
import secrets
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from random import Random
from typing import TYPE_CHECKING

from txtlocal.shared import telemetry
from txtlocal.shared.errors import BadRequest, GatewayTimeout, Internal
from txtlocal.shared.money import Micro, format_decimal, format_gbp
from txtlocal.shared.table import backoff
from txtlocal.slices.analytics.model import (
    CODE_ALPHABET,
    CODE_LENGTH,
    MAX_CODE_ATTEMPTS,
    MAX_PAGE_SIZE,
    MAX_REPORTING_MONTHS,
    ReportingPage,
    ReportingQuery,
    ReportingRow,
    RollupFeed,
    RollupSummary,
    TrackedLink,
    UsageLine,
    UsageTabPage,
    UsageTabRow,
    is_valid_code,
)
from txtlocal.slices.analytics.repo import (
    AnalyticsRepo,
    ClickQueries,
    ClickRows,
    UsageQueries,
    UsageRows,
)

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock
    from txtlocal.slices.messaging.model import Product

CLICKS_TIMEOUT_MESSAGE = "The clicks rollup query took too long"
CODE_COLLISION_MESSAGE = "could not allocate a tracked-link code after 8 attempts"
DECEMBER = 12
QUERY_DEADLINE = timedelta(seconds=300)
REPORTING_RANGE_INVERTED_MESSAGE = "since must be on or before until"
REPORTING_RANGE_MESSAGE = f"the date range spans at most {MAX_REPORTING_MONTHS} months"
REPORTING_COLUMNS = (
    "date",
    "product",
    "userId",
    "senderId",
    "country",
    "price",
    "quantity",
    "total",
)
URL_PATTERN = re.compile(r"https?://\S+")
USAGE_TIMEOUT_MESSAGE = "The usage rollup query took too long"


def months_between(since: date, until: date) -> list[str]:
    months: list[str] = []
    year, month = since.year, since.month
    while (year, month) <= (until.year, until.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year, month + 1) if month < DECEMBER else (year + 1, 1)
    return months


def month_span(month: str, since: date, until: date) -> tuple[str, str]:
    year, month_number = int(month[:4]), int(month[5:7])
    first_of_month = date(year, month_number, 1)
    next_month = (
        date(year, month_number + 1, 1) if month_number < DECEMBER else date(year + 1, 1, 1)
    )
    last_of_month = next_month - timedelta(days=1)
    return max(since, first_of_month).isoformat(), min(until, last_of_month).isoformat()


def matching(lines: Sequence[UsageLine], query: ReportingQuery) -> list[UsageLine]:
    countries = set(query.countries)
    products = set(query.products)
    sender_ids = set(query.sender_ids)
    user_ids = set(query.user_ids)

    return [
        line
        for line in lines
        if (not products or line.product in products)
        and (not user_ids or line.user_id in user_ids)
        and (not sender_ids or line.sender_id in sender_ids)
        and (not countries or line.country in countries)
    ]


def unit_price(line: UsageLine) -> Micro:
    return Micro(line.cost_micro // line.quantity) if line.quantity else Micro(0)


def reporting_row_of(line: UsageLine) -> ReportingRow:
    return ReportingRow(
        country=line.country,
        day=date.fromisoformat(line.day),
        price_micro=unit_price(line),
        product=line.product,
        quantity=line.quantity,
        sender_id=line.sender_id,
        total_micro=line.cost_micro,
        user_id=line.user_id,
    )


def csv_line(values: Sequence[object]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerow(values)
    return buffer.getvalue()


def reporting_csv_row(line: UsageLine) -> tuple[object, ...]:
    return (
        line.day,
        line.product,
        line.user_id,
        line.sender_id,
        line.country,
        format_decimal(unit_price(line)),
        line.quantity,
        format_gbp(Micro(line.cost_micro), 2).removeprefix("£"),
    )


def bounded(value: int, low: int, high: int) -> int:
    return min(max(value, low), high)


@dataclass(frozen=True, slots=True)
class AnalyticsService:
    click_queries: ClickQueries
    clock: Clock
    public_base_url: str
    repo: AnalyticsRepo
    usage_queries: UsageQueries
    rng: Random = field(default_factory=secrets.SystemRandom)

    async def shorten_urls(
        self, body: str, account_id: str, campaign_id: str, now: datetime
    ) -> str:
        urls = dict.fromkeys(match.group(0) for match in URL_PATTERN.finditer(body))
        if not urls:
            return body

        codes = {url: await self._fresh_code(url, account_id, campaign_id, now) for url in urls}
        return URL_PATTERN.sub(lambda match: self._short_link(codes[match.group(0)]), body)

    async def resolve_link(self, code: str) -> str | None:
        if not is_valid_code(code):
            telemetry.log("redirect_hit", code=code, hit=False)
            return None

        link = await self.repo.get_link(code)
        telemetry.log("redirect_hit", code=code, hit=link is not None)
        return None if link is None else link.url

    async def campaign_clicks_total(self, campaign_id: str) -> int:
        links = await self.repo.links_of_campaign(campaign_id)
        return sum(link.clicks_total for link in links)

    async def usage_month(self, account_id: str, month: str) -> UsageTabPage:
        totals: dict[tuple[Product, str], list[int]] = {}
        for line in await self.repo.usage_of_month(account_id, month):
            counted = totals.setdefault((line.product, line.user_id), [0, 0])
            counted[0] += line.quantity
            counted[1] += line.cost_micro

        rows = [
            UsageTabRow(
                cost_micro=Micro(cost_micro),
                month=month,
                product=product,
                quantity=quantity,
                user_id=user_id,
            )
            for (product, user_id), (quantity, cost_micro) in totals.items()
        ]
        return UsageTabPage(rows=rows)

    async def reporting(self, account_id: str, query: ReportingQuery) -> ReportingPage:
        rows = [reporting_row_of(line) for line in await self._reporting_lines(account_id, query)]
        page = max(query.page, 1)
        page_size = bounded(query.page_size, 1, MAX_PAGE_SIZE)
        start = (page - 1) * page_size
        return ReportingPage(
            page=page,
            page_size=page_size,
            rows=rows[start : start + page_size],
            total_results=len(rows),
        )

    async def reporting_csv(self, account_id: str, query: ReportingQuery) -> AsyncIterator[str]:
        yield csv_line(REPORTING_COLUMNS)
        for line in await self._reporting_lines(account_id, query):
            yield csv_line(reporting_csv_row(line))

    async def run_clicks_feed(self, day: date, *, force: bool = False) -> RollupSummary:
        return await self._run_feed(RollupFeed.CLICKS, day, force=force)

    async def run_usage_feed(self, day: date, *, force: bool = False) -> RollupSummary:
        return await self._run_feed(RollupFeed.USAGE, day, force=force)

    async def _run_feed(self, feed: RollupFeed, day: date, *, force: bool) -> RollupSummary:
        key = day.isoformat()
        if force:
            await self.repo.clear_rollup_marker(key, feed)
        if not await self.repo.claim_rollup_marker(key, feed, self.clock()):
            return RollupSummary(day=key)

        try:
            if feed is RollupFeed.CLICKS:
                return await self._do_clicks_feed(day)
            return await self._do_usage_feed(day)
        except Exception:
            await self.repo.clear_rollup_marker(key, feed)
            raise

    async def _do_clicks_feed(self, day: date) -> RollupSummary:
        result = await self._poll_clicks(await self.click_queries.start(day))
        now = self.clock()
        for row in result.rows:
            await self.repo.put_link_day(row.code, row.day, row.clicks, now)
            await self.repo.add_clicks_total(row.code, row.day, row.clicks)

        return RollupSummary(
            day=day.isoformat(),
            discarded_clicks=result.discarded,
            feeds=(RollupFeed.CLICKS,),
            link_rows=len(result.rows),
        )

    async def _do_usage_feed(self, day: date) -> RollupSummary:
        result = await self._poll_usage(await self.usage_queries.start(day))
        now = self.clock()
        for line in result.rows:
            await self.repo.put_usage_row(line, now)

        return RollupSummary(
            day=day.isoformat(),
            discarded_lines=result.discarded,
            feeds=(RollupFeed.USAGE,),
            usage_rows=len(result.rows),
        )

    async def _poll_clicks(self, query_id: str) -> ClickRows:
        deadline = self.clock() + QUERY_DEADLINE
        attempt = 0
        while self.clock() < deadline:
            result = await self.click_queries.poll(query_id)
            if isinstance(result, ClickRows):
                return result
            await asyncio.sleep(backoff(attempt))
            attempt += 1
        raise GatewayTimeout(CLICKS_TIMEOUT_MESSAGE)

    async def _poll_usage(self, query_id: str) -> UsageRows:
        deadline = self.clock() + QUERY_DEADLINE
        attempt = 0
        while self.clock() < deadline:
            result = await self.usage_queries.poll(query_id)
            if isinstance(result, UsageRows):
                return result
            await asyncio.sleep(backoff(attempt))
            attempt += 1
        raise GatewayTimeout(USAGE_TIMEOUT_MESSAGE)

    async def _reporting_lines(self, account_id: str, query: ReportingQuery) -> list[UsageLine]:
        if query.since > query.until:
            raise BadRequest(REPORTING_RANGE_INVERTED_MESSAGE)

        months = months_between(query.since, query.until)
        if len(months) > MAX_REPORTING_MONTHS:
            raise BadRequest(REPORTING_RANGE_MESSAGE)

        lines: list[UsageLine] = []
        for month in months:
            since_day, until_day = month_span(month, query.since, query.until)
            lines.extend(await self.repo.usage_of_month(account_id, month, since_day, until_day))

        return sorted(matching(lines, query), key=lambda line: line.day, reverse=True)

    async def _fresh_code(self, url: str, account_id: str, campaign_id: str, now: datetime) -> str:
        for _ in range(MAX_CODE_ATTEMPTS):
            code = self._random_code()
            link = TrackedLink(
                account_id=account_id,
                campaign_id=campaign_id,
                clicks_total=0,
                code=code,
                created_at=now,
                last_rollup=None,
                url=url,
            )
            if await self.repo.put_link(link):
                return code
        raise Internal(CODE_COLLISION_MESSAGE)

    def _random_code(self) -> str:
        return "".join(self.rng.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))

    def _short_link(self, code: str) -> str:
        return f"{self.public_base_url}/l/{code}"

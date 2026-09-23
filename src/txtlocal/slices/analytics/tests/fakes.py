from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from txtlocal.slices.analytics.model import RollupFeed, TrackedLink, UsageLine

if TYPE_CHECKING:
    from txtlocal.slices.analytics.repo import (
        AnalyticsRepo,
        ClickQueries,
        ClickResult,
        UsageQueries,
        UsageResult,
    )

NOW = datetime(2026, 9, 20, 2, 30, tzinfo=UTC)
ACCOUNT_ID = "acc_analytics"
CAMPAIGN_ID = "cmp_analytics"


def month_of(day: str) -> str:
    return day[:7]


@dataclass(slots=True)
class FakeAnalyticsRepo:
    gets: list[str] = field(default_factory=list)
    link_days_rows: dict[tuple[str, str], int] = field(default_factory=dict)
    links: dict[str, TrackedLink] = field(default_factory=dict)
    rollup_markers: set[tuple[str, RollupFeed]] = field(default_factory=set)
    usage_rows: list[UsageLine] = field(default_factory=list)

    async def put_link(self, link: TrackedLink) -> bool:
        if link.code in self.links:
            return False
        self.links[link.code] = link
        return True

    async def get_link(self, code: str) -> TrackedLink | None:
        self.gets.append(code)
        return self.links.get(code)

    async def links_of_campaign(self, campaign_id: str) -> list[TrackedLink]:
        return [link for link in self.links.values() if link.campaign_id == campaign_id]

    async def put_link_day(self, code: str, day: str, clicks: int, now: datetime) -> None:
        del now
        self.link_days_rows[(code, day)] = clicks

    async def add_clicks_total(self, code: str, day: str, clicks: int) -> bool:
        link = self.links.get(code)
        if link is None:
            return False
        if link.last_rollup is not None and link.last_rollup >= day:
            return False

        self.links[code] = TrackedLink(
            account_id=link.account_id,
            campaign_id=link.campaign_id,
            clicks_total=link.clicks_total + clicks,
            code=link.code,
            created_at=link.created_at,
            last_rollup=day,
            url=link.url,
        )
        return True

    async def link_days(
        self, codes: Sequence[str], since: date, until: date
    ) -> dict[str, dict[str, int]]:
        span = (until - since).days + 1
        days = [(since + timedelta(days=offset)).isoformat() for offset in range(span)]

        result: dict[str, dict[str, int]] = {code: {} for code in codes}
        for code in codes:
            for day in days:
                clicks = self.link_days_rows.get((code, day))
                if clicks is not None:
                    result[code][day] = clicks
        return result

    async def put_usage_row(self, line: UsageLine, now: datetime) -> None:
        del now
        self.usage_rows = [row for row in self.usage_rows if not _same_row(row, line)]
        self.usage_rows.append(line)

    async def usage_of_month(
        self,
        account_id: str,
        month: str,
        since_day: str | None = None,
        until_day: str | None = None,
    ) -> list[UsageLine]:
        rows = [
            row
            for row in self.usage_rows
            if row.account_id == account_id and month_of(row.day) == month
        ]
        if since_day is None or until_day is None:
            return rows
        return [row for row in rows if since_day <= row.day <= until_day]

    async def claim_rollup_marker(self, day: str, feed: RollupFeed, now: datetime) -> bool:
        del now
        marker = (day, feed)
        if marker in self.rollup_markers:
            return False
        self.rollup_markers.add(marker)
        return True

    async def clear_rollup_marker(self, day: str, feed: RollupFeed) -> None:
        self.rollup_markers.discard((day, feed))


def _same_row(a: UsageLine, b: UsageLine) -> bool:
    return (
        a.account_id == b.account_id
        and a.day == b.day
        and a.product == b.product
        and a.sender_id == b.sender_id
        and a.country == b.country
        and a.user_id == b.user_id
    )


def _fits_repo(fake: FakeAnalyticsRepo) -> AnalyticsRepo:
    return fake


@dataclass(slots=True)
class FakeUsageQueries:
    results: list[UsageResult]
    started: list[date] = field(default_factory=list)

    async def start(self, day: date) -> str:
        self.started.append(day)
        return "usage-query"

    async def poll(self, query_id: str) -> UsageResult:
        del query_id
        return self.results.pop(0)


def _fits_usage_queries(fake: FakeUsageQueries) -> UsageQueries:
    return fake


@dataclass(slots=True)
class FakeClickQueries:
    results: list[ClickResult]
    started: list[date] = field(default_factory=list)

    async def start(self, day: date) -> str:
        self.started.append(day)
        return "click-query"

    async def poll(self, query_id: str) -> ClickResult:
        del query_id
        return self.results.pop(0)


def _fits_click_queries(fake: FakeClickQueries) -> ClickQueries:
    return fake


def clock_after(step: timedelta) -> AdvancingClock:
    return AdvancingClock(now=NOW, step=step)


@dataclass(slots=True)
class AdvancingClock:
    now: datetime
    step: timedelta

    def __call__(self) -> datetime:
        current = self.now
        self.now += self.step
        return current

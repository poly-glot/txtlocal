from dataclasses import dataclass, replace
from datetime import date, timedelta
from random import Random
from typing import TYPE_CHECKING

import pytest

from txtlocal.shared.errors import BadRequest, GatewayTimeout, Internal
from txtlocal.shared.money import Micro
from txtlocal.slices.analytics.model import (
    MAX_CODE_ATTEMPTS,
    MAX_PAGE_SIZE,
    MAX_REPORTING_MONTHS,
    ClickDay,
    ReportingQuery,
    RollupFeed,
    TrackedLink,
    UsageLine,
)
from txtlocal.slices.analytics.repo import (
    ClickQueries,
    ClickRows,
    UsageQueries,
    UsageResult,
    UsageRows,
)
from txtlocal.slices.analytics.service import (
    CLICKS_TIMEOUT_MESSAGE,
    CODE_COLLISION_MESSAGE,
    REPORTING_RANGE_INVERTED_MESSAGE,
    REPORTING_RANGE_MESSAGE,
    USAGE_TIMEOUT_MESSAGE,
    AnalyticsService,
    months_between,
)
from txtlocal.slices.analytics.tests.fakes import (
    ACCOUNT_ID,
    CAMPAIGN_ID,
    NOW,
    FakeAnalyticsRepo,
    FakeClickQueries,
    FakeUsageQueries,
    clock_after,
)
from txtlocal.slices.messaging.model import Product

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock

PUBLIC_BASE_URL = "https://app.txtlocal.example"


def service_over(
    repo: FakeAnalyticsRepo | None = None,
    click_queries: ClickQueries | None = None,
    usage_queries: UsageQueries | None = None,
    clock: Clock | None = None,
    rng: Random | None = None,
) -> AnalyticsService:
    return AnalyticsService(
        click_queries=click_queries or FakeClickQueries(results=[]),
        clock=clock or (lambda: NOW),
        public_base_url=PUBLIC_BASE_URL,
        repo=repo or FakeAnalyticsRepo(),
        rng=rng or Random(1),
        usage_queries=usage_queries or FakeUsageQueries(results=[]),
    )


def a_link(code: str, campaign_id: str = CAMPAIGN_ID, clicks_total: int = 0) -> TrackedLink:
    return TrackedLink(
        account_id=ACCOUNT_ID,
        campaign_id=campaign_id,
        clicks_total=clicks_total,
        code=code,
        created_at=NOW,
        last_rollup=None,
        url="https://example.com/original",
    )


async def test_shorten_urls_leaves_a_body_with_no_url_unchanged() -> None:
    repo = FakeAnalyticsRepo()
    body = "Your code is 1234, thanks!"

    result = await service_over(repo).shorten_urls(body, ACCOUNT_ID, CAMPAIGN_ID, NOW)

    assert result == body
    assert repo.links == {}


async def test_shorten_urls_replaces_a_single_url() -> None:
    repo = FakeAnalyticsRepo()
    body = "Track your order at https://example.com/track/123"

    result = await service_over(repo).shorten_urls(body, ACCOUNT_ID, CAMPAIGN_ID, NOW)

    assert len(repo.links) == 1
    link = next(iter(repo.links.values()))
    assert link.url == "https://example.com/track/123"
    assert link.account_id == ACCOUNT_ID
    assert link.campaign_id == CAMPAIGN_ID
    assert result == f"Track your order at {PUBLIC_BASE_URL}/l/{link.code}"


async def test_shorten_urls_makes_one_row_per_distinct_url() -> None:
    repo = FakeAnalyticsRepo()
    body = "See https://a.example/x and https://b.example/y"

    await service_over(repo).shorten_urls(body, ACCOUNT_ID, CAMPAIGN_ID, NOW)

    assert {link.url for link in repo.links.values()} == {
        "https://a.example/x",
        "https://b.example/y",
    }
    assert len(repo.links) == 2


async def test_shorten_urls_reuses_one_code_for_a_url_repeated_in_the_body() -> None:
    repo = FakeAnalyticsRepo()
    body = "https://a.example/x again https://a.example/x"

    result = await service_over(repo).shorten_urls(body, ACCOUNT_ID, CAMPAIGN_ID, NOW)

    assert len(repo.links) == 1
    code = next(iter(repo.links))
    assert result == f"{PUBLIC_BASE_URL}/l/{code} again {PUBLIC_BASE_URL}/l/{code}"


@dataclass(slots=True)
class CollidesNTimesRepo(FakeAnalyticsRepo):
    fail_times: int = 0
    attempts: int = 0

    async def put_link(self, link: TrackedLink) -> bool:
        self.attempts += 1
        if self.attempts <= self.fail_times:
            return False
        return await super().put_link(link)


async def test_shorten_urls_succeeds_on_the_last_allowed_attempt() -> None:
    repo = CollidesNTimesRepo(fail_times=MAX_CODE_ATTEMPTS - 1)

    await service_over(repo).shorten_urls("https://a.example/x", ACCOUNT_ID, CAMPAIGN_ID, NOW)

    assert repo.attempts == MAX_CODE_ATTEMPTS
    assert len(repo.links) == 1


async def test_shorten_urls_raises_after_exhausting_every_attempt() -> None:
    repo = CollidesNTimesRepo(fail_times=MAX_CODE_ATTEMPTS)

    with pytest.raises(Internal) as caught:
        await service_over(repo).shorten_urls("https://a.example/x", ACCOUNT_ID, CAMPAIGN_ID, NOW)

    assert str(caught.value) == CODE_COLLISION_MESSAGE
    assert repo.attempts == MAX_CODE_ATTEMPTS


async def test_resolve_link_rejects_a_malformed_code_before_any_table_read() -> None:
    repo = FakeAnalyticsRepo()

    resolved = await service_over(repo).resolve_link("too-short")

    assert resolved is None
    assert repo.gets == []


async def test_resolve_link_answers_none_for_an_unknown_code() -> None:
    resolved = await service_over(FakeAnalyticsRepo()).resolve_link("ab3de5fgh7")
    assert resolved is None


async def test_resolve_link_answers_the_url_for_a_known_code() -> None:
    repo = FakeAnalyticsRepo(links={"ab3de5fgh7": a_link("ab3de5fgh7")})

    resolved = await service_over(repo).resolve_link("ab3de5fgh7")

    assert resolved == "https://example.com/original"


async def test_campaign_clicks_total_sums_every_link_on_the_campaign() -> None:
    repo = FakeAnalyticsRepo(
        links={
            "link0000a": a_link("link0000a", clicks_total=3),
            "link0000b": a_link("link0000b", clicks_total=5),
            "link0000c": a_link("link0000c", campaign_id="other-campaign", clicks_total=99),
        }
    )

    total = await service_over(repo).campaign_clicks_total(CAMPAIGN_ID)

    assert total == 8


def usage_row(
    user_id: str, product: str, sender_id: str, country: str, quantity: int, cost: int
) -> UsageLine:
    return UsageLine(
        account_id=ACCOUNT_ID,
        cost_micro=Micro(cost),
        country=country,
        day="2026-09-18",
        product=Product(product),
        quantity=quantity,
        sender_id=sender_id,
        user_id=user_id,
    )


async def test_usage_month_sums_across_sender_and_country_for_the_same_product_and_user() -> None:
    repo = FakeAnalyticsRepo(
        usage_rows=[
            usage_row("usr-1", "SMS", "snd-1", "GB", 2, 85400),
            usage_row("usr-1", "SMS", "snd-2", "US", 1, 100000),
            usage_row("usr-2", "SMS", "snd-1", "GB", 1, 42700),
        ]
    )

    page = await service_over(repo).usage_month(ACCOUNT_ID, "2026-09")

    by_user = {row.user_id: row for row in page.rows}
    assert by_user["usr-1"].quantity == 3
    assert by_user["usr-1"].cost_micro == 185400
    assert by_user["usr-2"].quantity == 1
    assert by_user["usr-2"].cost_micro == 42700


def reporting_query(**overrides: object) -> ReportingQuery:
    base: dict[str, object] = {"since": date(2026, 7, 1), "until": date(2026, 9, 18)}
    base.update(overrides)
    return ReportingQuery.model_validate(base)


async def test_reporting_filters_by_product_sender_country_and_user() -> None:
    repo = FakeAnalyticsRepo(
        usage_rows=[
            usage_row("usr-1", "SMS", "snd-1", "GB", 1, 42700),
            usage_row("usr-1", "MMS", "snd-1", "GB", 1, 42700),
            usage_row("usr-2", "SMS", "snd-2", "US", 1, 42700),
        ]
    )

    page = await service_over(repo).reporting(
        ACCOUNT_ID,
        reporting_query(
            products=["SMS"], sender_ids=["snd-1"], countries=["GB"], user_ids=["usr-1"]
        ),
    )

    assert len(page.rows) == 1
    assert (page.rows[0].product, page.rows[0].sender_id, page.rows[0].country) == (
        "SMS",
        "snd-1",
        "GB",
    )


async def test_reporting_sorts_newest_day_first_and_paginates() -> None:
    repo = FakeAnalyticsRepo(
        usage_rows=[
            UsageLine(
                account_id=ACCOUNT_ID,
                cost_micro=Micro(42700),
                country="GB",
                day=f"2026-09-{day:02d}",
                product=Product.SMS,
                quantity=1,
                sender_id="snd-1",
                user_id="usr-1",
            )
            for day in (14, 15, 16)
        ]
    )

    page = await service_over(repo).reporting(ACCOUNT_ID, reporting_query(page=1, page_size=2))

    assert page.total_results == 3
    assert [row.day.isoformat() for row in page.rows] == ["2026-09-16", "2026-09-15"]


async def test_reporting_keeps_a_page_size_at_the_maximum() -> None:
    page = await service_over(FakeAnalyticsRepo()).reporting(
        ACCOUNT_ID, reporting_query(page_size=MAX_PAGE_SIZE)
    )
    assert page.page_size == MAX_PAGE_SIZE


async def test_reporting_clamps_a_page_size_over_the_maximum() -> None:
    page = await service_over(FakeAnalyticsRepo()).reporting(
        ACCOUNT_ID, reporting_query(page_size=MAX_PAGE_SIZE + 1)
    )
    assert page.page_size == MAX_PAGE_SIZE


async def test_reporting_clamps_a_page_below_one() -> None:
    page = await service_over(FakeAnalyticsRepo()).reporting(ACCOUNT_ID, reporting_query(page=0))
    assert page.page == 1


async def test_reporting_rejects_an_inverted_range() -> None:
    with pytest.raises(BadRequest) as caught:
        await service_over(FakeAnalyticsRepo()).reporting(
            ACCOUNT_ID, reporting_query(since=date(2026, 9, 18), until=date(2026, 9, 1))
        )
    assert str(caught.value) == REPORTING_RANGE_INVERTED_MESSAGE


async def test_reporting_allows_a_range_spanning_exactly_four_months() -> None:
    page = await service_over(FakeAnalyticsRepo()).reporting(
        ACCOUNT_ID, reporting_query(since=date(2026, 6, 1), until=date(2026, 9, 18))
    )
    assert page.total_results == 0


async def test_reporting_rejects_a_range_spanning_five_months() -> None:
    with pytest.raises(BadRequest) as caught:
        await service_over(FakeAnalyticsRepo()).reporting(
            ACCOUNT_ID, reporting_query(since=date(2026, 5, 1), until=date(2026, 9, 18))
        )
    assert str(caught.value) == REPORTING_RANGE_MESSAGE
    assert MAX_REPORTING_MONTHS == 4


def test_months_between_crosses_a_year_boundary() -> None:
    assert months_between(date(2026, 11, 15), date(2027, 1, 15)) == [
        "2026-11",
        "2026-12",
        "2027-01",
    ]


async def test_reporting_csv_rounds_total_to_two_places_but_the_api_keeps_micro() -> None:
    repo = FakeAnalyticsRepo(usage_rows=[usage_row("usr-1", "SMS", "snd-1", "GB", 1, 42700)])
    service = service_over(repo)

    page = await service.reporting(ACCOUNT_ID, reporting_query())
    csv_lines = [line async for line in service.reporting_csv(ACCOUNT_ID, reporting_query())]

    assert page.rows[0].total_micro == 42700
    assert csv_lines[1].strip() == "2026-09-18,SMS,usr-1,snd-1,GB,0.0427,1,0.04"


@pytest.mark.parametrize(
    ("quantity", "cost_micro", "price_micro"),
    [(1, 42700, 42700), (2, 85400, 42700), (3, 100000, 33333), (0, 0, 0)],
    ids=["single-message", "even-split", "floors-the-remainder", "no-messages-prices-zero"],
)
async def test_reporting_row_answers_unit_price_and_total_in_micro(
    quantity: int, cost_micro: int, price_micro: int
) -> None:
    repo = FakeAnalyticsRepo(
        usage_rows=[usage_row("usr-1", "SMS", "snd-1", "GB", quantity, cost_micro)]
    )

    page = await service_over(repo).reporting(ACCOUNT_ID, reporting_query())

    assert (page.rows[0].price_micro, page.rows[0].total_micro) == (price_micro, cost_micro)


async def test_run_usage_feed_writes_rows_and_the_summary() -> None:
    repo = FakeAnalyticsRepo()
    usage_queries = FakeUsageQueries(
        results=[UsageRows(discarded=1, rows=[usage_row("usr-1", "SMS", "snd-1", "GB", 1, 42700)])]
    )

    summary = await service_over(repo, usage_queries=usage_queries).run_usage_feed(
        date(2026, 9, 18)
    )

    assert summary.usage_rows == 1
    assert summary.discarded_lines == 1
    assert summary.feeds == (RollupFeed.USAGE,)
    assert len(repo.usage_rows) == 1
    assert (repo.rollup_markers) == {("2026-09-18", RollupFeed.USAGE)}
    assert usage_queries.started == [date(2026, 9, 18)]


async def test_run_usage_feed_skips_a_day_already_marked_done() -> None:
    repo = FakeAnalyticsRepo(rollup_markers={("2026-09-18", RollupFeed.USAGE)})
    usage_queries = FakeUsageQueries(results=[])

    summary = await service_over(repo, usage_queries=usage_queries).run_usage_feed(
        date(2026, 9, 18)
    )

    assert summary.feeds == ()
    assert usage_queries.started == []


async def test_run_usage_feed_force_reruns_a_day_already_marked_done() -> None:
    repo = FakeAnalyticsRepo(rollup_markers={("2026-09-18", RollupFeed.USAGE)})
    usage_queries = FakeUsageQueries(results=[UsageRows(discarded=0, rows=[])])

    summary = await service_over(repo, usage_queries=usage_queries).run_usage_feed(
        date(2026, 9, 18), force=True
    )

    assert summary.feeds == (RollupFeed.USAGE,)
    assert usage_queries.started == [date(2026, 9, 18)]


@dataclass(slots=True)
class ExplodingUsageQueries:
    async def start(self, day: date) -> str:
        del day
        return "boom"

    async def poll(self, query_id: str) -> UsageResult:
        del query_id
        raise Internal("usage query failed")


async def test_run_usage_feed_clears_its_marker_and_reraises_on_failure() -> None:
    repo = FakeAnalyticsRepo()

    with pytest.raises(Internal):
        await service_over(repo, usage_queries=ExplodingUsageQueries()).run_usage_feed(
            date(2026, 9, 18)
        )

    assert repo.rollup_markers == set()


async def test_run_usage_feed_raises_gateway_timeout_past_the_deadline() -> None:
    repo = FakeAnalyticsRepo()
    service = service_over(
        repo, usage_queries=FakeUsageQueries(results=[]), clock=clock_after(timedelta(seconds=301))
    )

    with pytest.raises(GatewayTimeout) as caught:
        await service.run_usage_feed(date(2026, 9, 18))

    assert str(caught.value) == USAGE_TIMEOUT_MESSAGE


async def test_run_clicks_feed_writes_link_days_and_totals() -> None:
    repo = FakeAnalyticsRepo(links={"ab3de5fgh7": a_link("ab3de5fgh7", clicks_total=1)})
    click_queries = FakeClickQueries(
        results=[
            ClickRows(discarded=2, rows=[ClickDay(clicks=5, code="ab3de5fgh7", day="2026-09-18")])
        ]
    )

    summary = await service_over(repo, click_queries=click_queries).run_clicks_feed(
        date(2026, 9, 18)
    )

    assert summary.link_rows == 1
    assert summary.discarded_clicks == 2
    assert summary.feeds == (RollupFeed.CLICKS,)
    assert repo.link_days_rows[("ab3de5fgh7", "2026-09-18")] == 5
    assert repo.links["ab3de5fgh7"].clicks_total == 6


async def test_run_clicks_feed_does_not_double_count_a_replayed_day() -> None:
    link = replace(a_link("ab3de5fgh7", clicks_total=5), last_rollup="2026-09-18")
    repo = FakeAnalyticsRepo(links={"ab3de5fgh7": link})
    click_queries = FakeClickQueries(
        results=[
            ClickRows(discarded=0, rows=[ClickDay(clicks=9, code="ab3de5fgh7", day="2026-09-18")])
        ]
    )

    await service_over(repo, click_queries=click_queries, clock=lambda: NOW).run_clicks_feed(
        date(2026, 9, 18), force=True
    )

    assert repo.links["ab3de5fgh7"].clicks_total == 5
    assert repo.link_days_rows[("ab3de5fgh7", "2026-09-18")] == 9


async def test_run_clicks_feed_raises_gateway_timeout_past_the_deadline() -> None:
    service = service_over(
        FakeAnalyticsRepo(),
        click_queries=FakeClickQueries(results=[]),
        clock=clock_after(timedelta(seconds=301)),
    )

    with pytest.raises(GatewayTimeout) as caught:
        await service.run_clicks_feed(date(2026, 9, 18))

    assert str(caught.value) == CLICKS_TIMEOUT_MESSAGE

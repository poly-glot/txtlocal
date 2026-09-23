from datetime import UTC, date, datetime

from txtlocal.shared.money import Micro
from txtlocal.shared.testing import local_repo_table
from txtlocal.slices.analytics.model import RollupFeed, TrackedLink, UsageLine
from txtlocal.slices.analytics.repo import AnalyticsDynamoRepo
from txtlocal.slices.messaging.model import Product

NOW = datetime(2026, 9, 20, 2, 30, tzinfo=UTC)
ACCOUNT_ID = "acc_repo_1"
CAMPAIGN_ID = "cmp_repo_1"

LINKS_PAST_ONE_PAGE = 6
ROWS_PAST_ONE_PAGE = 800
SORT_KEY_FILLER = 400
URL_FILLER = 300_000


def a_link(code: str, campaign_id: str = CAMPAIGN_ID) -> TrackedLink:
    return TrackedLink(
        account_id=ACCOUNT_ID,
        campaign_id=campaign_id,
        clicks_total=0,
        code=code,
        created_at=NOW,
        last_rollup=None,
        url="https://example.com/original",
    )


def a_wide_link(index: int) -> TrackedLink:
    return TrackedLink(
        account_id=ACCOUNT_ID,
        campaign_id=CAMPAIGN_ID,
        clicks_total=0,
        code=f"wide{index:06d}",
        created_at=NOW,
        last_rollup=None,
        url=f"https://example.com/{'w' * URL_FILLER}",
    )


async def test_put_link_is_put_if_absent() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)

        assert await repo.put_link(a_link("ab3de5fgh7")) is True
        assert await repo.put_link(a_link("ab3de5fgh7")) is False


async def test_get_link_answers_none_for_an_unknown_code() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)
        assert await repo.get_link("ab3de5fgh7") is None


async def test_get_link_round_trips_every_field() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)
        link = a_link("ab3de5fgh7")
        await repo.put_link(link)

        found = await repo.get_link("ab3de5fgh7")

        assert found == link


async def test_links_of_campaign_lists_only_that_campaigns_links() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)
        await repo.put_link(a_link("ab3de5fgh7"))
        await repo.put_link(a_link("zz3de5fgh7"))
        await repo.put_link(a_link("other00001", campaign_id="cmp_other"))

        found = {link.code for link in await repo.links_of_campaign(CAMPAIGN_ID)}

        assert found == {"ab3de5fgh7", "zz3de5fgh7"}


async def test_links_of_campaign_reads_past_the_first_page() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)
        for index in range(LINKS_PAST_ONE_PAGE):
            await repo.put_link(a_wide_link(index))

        found = await repo.links_of_campaign(CAMPAIGN_ID)

        assert len(found) == LINKS_PAST_ONE_PAGE


async def test_add_clicks_total_requires_the_link_to_exist() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)
        assert await repo.add_clicks_total("ab3de5fgh7", "2026-09-18", 5) is False


async def test_add_clicks_total_accumulates_on_a_newer_day() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)
        await repo.put_link(a_link("ab3de5fgh7"))

        assert await repo.add_clicks_total("ab3de5fgh7", "2026-09-18", 5) is True
        assert await repo.add_clicks_total("ab3de5fgh7", "2026-09-19", 3) is True

        found = await repo.get_link("ab3de5fgh7")
        assert found is not None
        assert (found.clicks_total, found.last_rollup) == (8, "2026-09-19")


async def test_add_clicks_total_refuses_a_replay_of_an_older_day() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)
        await repo.put_link(a_link("ab3de5fgh7"))
        await repo.add_clicks_total("ab3de5fgh7", "2026-09-19", 3)

        assert await repo.add_clicks_total("ab3de5fgh7", "2026-09-18", 5) is False

        found = await repo.get_link("ab3de5fgh7")
        assert found is not None
        assert found.clicks_total == 3


async def test_link_days_reads_a_chunked_window_and_leaves_gaps_absent() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)
        await repo.put_link_day("ab3de5fgh7", "2026-09-18", 4, NOW)
        await repo.put_link_day("ab3de5fgh7", "2026-09-20", 2, NOW)

        found = await repo.link_days(["ab3de5fgh7"], date(2026, 9, 17), date(2026, 9, 20))

        assert found == {"ab3de5fgh7": {"2026-09-18": 4, "2026-09-20": 2}}


async def test_put_link_day_overwrites_on_replay() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)
        await repo.put_link_day("ab3de5fgh7", "2026-09-18", 4, NOW)
        await repo.put_link_day("ab3de5fgh7", "2026-09-18", 9, NOW)

        found = await repo.link_days(["ab3de5fgh7"], date(2026, 9, 18), date(2026, 9, 18))

        assert found == {"ab3de5fgh7": {"2026-09-18": 9}}


def a_usage_line(day: str, sender_id: str = "snd-1", country: str = "GB") -> UsageLine:
    return UsageLine(
        account_id=ACCOUNT_ID,
        cost_micro=Micro(42700),
        country=country,
        day=day,
        product=Product.SMS,
        quantity=1,
        sender_id=sender_id,
        user_id="usr-1",
    )


def a_wide_usage_line(index: int) -> UsageLine:
    return a_usage_line(
        "2026-09-01",
        country="G" * SORT_KEY_FILLER,
        sender_id=f"snd-{index:04d}{'w' * SORT_KEY_FILLER}",
    )


async def test_usage_of_month_reads_the_whole_partition_with_no_day_bounds() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)
        await repo.put_usage_row(a_usage_line("2026-09-01"), NOW)
        await repo.put_usage_row(a_usage_line("2026-09-30"), NOW)

        found = await repo.usage_of_month(ACCOUNT_ID, "2026-09")

        assert {row.day for row in found} == {"2026-09-01", "2026-09-30"}


async def test_usage_of_month_narrows_to_a_day_range() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)
        await repo.put_usage_row(a_usage_line("2026-09-01"), NOW)
        await repo.put_usage_row(a_usage_line("2026-09-15"), NOW)
        await repo.put_usage_row(a_usage_line("2026-09-30"), NOW)

        found = await repo.usage_of_month(ACCOUNT_ID, "2026-09", "2026-09-10", "2026-09-20")

        assert [row.day for row in found] == ["2026-09-15"]


async def test_usage_of_month_reads_past_the_first_page() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)
        for index in range(ROWS_PAST_ONE_PAGE):
            await repo.put_usage_row(a_wide_usage_line(index), NOW)

        found = await repo.usage_of_month(ACCOUNT_ID, "2026-09")

        assert len(found) == ROWS_PAST_ONE_PAGE


async def test_put_usage_row_overwrites_a_replayed_day() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)
        await repo.put_usage_row(a_usage_line("2026-09-18"), NOW)
        await repo.put_usage_row(
            UsageLine(
                account_id=ACCOUNT_ID,
                cost_micro=Micro(99999),
                country="GB",
                day="2026-09-18",
                product=Product.SMS,
                quantity=7,
                sender_id="snd-1",
                user_id="usr-1",
            ),
            NOW,
        )

        found = await repo.usage_of_month(ACCOUNT_ID, "2026-09")

        assert len(found) == 1
        assert (found[0].quantity, found[0].cost_micro) == (7, 99999)


async def test_claim_rollup_marker_is_put_if_absent() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)

        assert await repo.claim_rollup_marker("2026-09-18", RollupFeed.USAGE, NOW) is True
        assert await repo.claim_rollup_marker("2026-09-18", RollupFeed.USAGE, NOW) is False


async def test_claim_rollup_marker_is_independent_per_feed() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)

        assert await repo.claim_rollup_marker("2026-09-18", RollupFeed.USAGE, NOW) is True
        assert await repo.claim_rollup_marker("2026-09-18", RollupFeed.CLICKS, NOW) is True


async def test_clear_rollup_marker_allows_reclaiming() -> None:
    async with local_repo_table("analytics") as table:
        repo = AnalyticsDynamoRepo(table)
        await repo.claim_rollup_marker("2026-09-18", RollupFeed.USAGE, NOW)

        await repo.clear_rollup_marker("2026-09-18", RollupFeed.USAGE)

        assert await repo.claim_rollup_marker("2026-09-18", RollupFeed.USAGE, NOW) is True

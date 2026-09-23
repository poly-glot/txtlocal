from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from txtlocal.entrypoints.rollup import Analytics, Rollup, combined, day_of_event, feeds_of_event
from txtlocal.slices.analytics.model import RollupFeed, RollupSummary

NOW = datetime(2026, 9, 20, 2, 30, tzinfo=UTC)
EMPTY = RollupSummary(day="")


@dataclass(slots=True)
class FakeAnalytics:
    click_calls: list[tuple[date, bool]] = field(default_factory=list)
    click_result: RollupSummary = EMPTY
    usage_calls: list[tuple[date, bool]] = field(default_factory=list)
    usage_result: RollupSummary = EMPTY

    async def run_clicks_feed(self, day: date, *, force: bool = False) -> RollupSummary:
        self.click_calls.append((day, force))
        return self.click_result

    async def run_usage_feed(self, day: date, *, force: bool = False) -> RollupSummary:
        self.usage_calls.append((day, force))
        return self.usage_result


def _fits(fake: FakeAnalytics) -> Analytics:
    return fake


def rollup_over(analytics: FakeAnalytics) -> Rollup:
    return Rollup(analytics=analytics, clock=lambda: NOW)


async def test_run_defaults_to_yesterday_and_both_feeds_unforced() -> None:
    analytics = FakeAnalytics()

    await rollup_over(analytics).run(None, None)

    assert analytics.click_calls == [(date(2026, 9, 19), False)]
    assert analytics.usage_calls == [(date(2026, 9, 19), False)]


async def test_run_uses_the_given_day() -> None:
    analytics = FakeAnalytics()

    await rollup_over(analytics).run(date(2026, 9, 1), None)

    assert analytics.click_calls == [(date(2026, 9, 1), False)]
    assert analytics.usage_calls == [(date(2026, 9, 1), False)]


async def test_run_with_named_feeds_forces_only_those_feeds() -> None:
    analytics = FakeAnalytics()

    await rollup_over(analytics).run(date(2026, 9, 18), [RollupFeed.USAGE])

    assert analytics.click_calls == []
    assert analytics.usage_calls == [(date(2026, 9, 18), True)]


async def test_run_combines_the_summary_across_feeds() -> None:
    analytics = FakeAnalytics(
        click_result=RollupSummary(
            day="x", discarded_clicks=2, feeds=(RollupFeed.CLICKS,), link_rows=3
        ),
        usage_result=RollupSummary(
            day="x", discarded_lines=1, feeds=(RollupFeed.USAGE,), usage_rows=5
        ),
    )

    summary = await rollup_over(analytics).run(date(2026, 9, 18), None)

    assert summary == RollupSummary(
        day="2026-09-18",
        discarded_clicks=2,
        discarded_lines=1,
        feeds=(RollupFeed.CLICKS, RollupFeed.USAGE),
        link_rows=3,
        usage_rows=5,
    )


def test_day_of_event_defaults_to_yesterday() -> None:
    assert day_of_event({}, lambda: NOW) == date(2026, 9, 19)


def test_day_of_event_parses_an_explicit_date() -> None:
    assert day_of_event({"date": "2026-09-01"}, lambda: NOW) == date(2026, 9, 1)


def test_feeds_of_event_defaults_to_none() -> None:
    assert feeds_of_event({}) is None


def test_feeds_of_event_parses_named_feeds() -> None:
    assert feeds_of_event({"feeds": ["usage"]}) == [RollupFeed.USAGE]


def test_combined_sums_every_field_across_feeds() -> None:
    result = combined(
        "2026-09-18",
        [
            RollupSummary(day="x", discarded_clicks=1, feeds=(RollupFeed.CLICKS,), link_rows=2),
            RollupSummary(day="x", discarded_lines=3, feeds=(RollupFeed.USAGE,), usage_rows=4),
        ],
    )

    assert result == RollupSummary(
        day="2026-09-18",
        discarded_clicks=1,
        discarded_lines=3,
        feeds=(RollupFeed.CLICKS, RollupFeed.USAGE),
        link_rows=2,
        usage_rows=4,
    )


def test_combined_of_no_summaries_is_empty() -> None:
    assert combined("2026-09-18", []) == RollupSummary(day="2026-09-18")

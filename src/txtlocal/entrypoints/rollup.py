from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Protocol, TypedDict, assert_never

from txtlocal.entrypoints import wiring
from txtlocal.shared import runtime, telemetry
from txtlocal.shared.clock import utc_now
from txtlocal.slices.analytics.model import RollupFeed, RollupSummary

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock


class RollupEvent(TypedDict, total=False):
    date: str
    feeds: list[str]


class Analytics(Protocol):
    async def run_clicks_feed(self, day: date, *, force: bool = False) -> RollupSummary: ...

    async def run_usage_feed(self, day: date, *, force: bool = False) -> RollupSummary: ...


def day_of_event(event: RollupEvent, clock: Clock) -> date:
    raw = event.get("date")
    return date.fromisoformat(raw) if raw else clock().date() - timedelta(days=1)


def feeds_of_event(event: RollupEvent) -> list[RollupFeed] | None:
    raw = event.get("feeds")
    return None if raw is None else [RollupFeed(value) for value in raw]


def combined(day: str, summaries: Sequence[RollupSummary]) -> RollupSummary:
    return RollupSummary(
        day=day,
        discarded_clicks=sum(summary.discarded_clicks for summary in summaries),
        discarded_lines=sum(summary.discarded_lines for summary in summaries),
        feeds=tuple(feed for summary in summaries for feed in summary.feeds),
        link_rows=sum(summary.link_rows for summary in summaries),
        usage_rows=sum(summary.usage_rows for summary in summaries),
    )


@dataclass(frozen=True, slots=True)
class Rollup:
    analytics: Analytics
    clock: Clock

    async def run(self, day: date | None, feeds: Sequence[RollupFeed] | None) -> RollupSummary:
        target_day = day or self.clock().date() - timedelta(days=1)
        force = feeds is not None
        chosen = feeds or (RollupFeed.CLICKS, RollupFeed.USAGE)

        summaries = [await self._run_one(feed, target_day, force=force) for feed in chosen]
        summary = combined(target_day.isoformat(), summaries)

        telemetry.log(
            "rollup_done",
            day=summary.day,
            discarded_clicks=summary.discarded_clicks,
            discarded_lines=summary.discarded_lines,
            feeds=[feed.value for feed in summary.feeds],
            link_rows=summary.link_rows,
            usage_rows=summary.usage_rows,
        )
        return summary

    async def _run_one(self, feed: RollupFeed, day: date, *, force: bool) -> RollupSummary:
        match feed:
            case RollupFeed.CLICKS:
                return await self.analytics.run_clicks_feed(day, force=force)
            case RollupFeed.USAGE:
                return await self.analytics.run_usage_feed(day, force=force)
            case _ as unreachable:
                assert_never(unreachable)


def rollup() -> Rollup:
    return Rollup(analytics=wiring.analytics(), clock=utc_now)


def handler(event: RollupEvent | None, _context: object) -> None:
    payload = event or RollupEvent()
    built = rollup()
    runtime.run(built.run(day_of_event(payload, built.clock), feeds_of_event(payload)))


def main() -> None:
    runtime.run(rollup().run(None, None))


telemetry.configure()

if __name__ == "__main__":
    main()

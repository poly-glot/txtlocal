from dataclasses import dataclass, field
from datetime import UTC, datetime

from txtlocal.entrypoints.scheduler import Scheduler
from txtlocal.shared.errors import NotFound, Upstream
from txtlocal.shared.money import Micro
from txtlocal.slices.campaigns.model import CampaignRef, FanOut, Settled
from txtlocal.slices.campaigns.service import DUE_LIMIT

ACCOUNT = "account-1"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def ref(campaign_id: str) -> CampaignRef:
    return CampaignRef(account_id=ACCOUNT, campaign_id=campaign_id)


@dataclass(slots=True)
class FakeCampaigns:
    ready: list[CampaignRef] = field(default_factory=list)
    stalled: list[CampaignRef] = field(default_factory=list)
    lost: frozenset[str] = frozenset()
    poisoned: frozenset[str] = frozenset()
    unsettleable: frozenset[str] = frozenset()
    claimed: list[tuple[CampaignRef, datetime]] = field(default_factory=list)
    settled: list[tuple[CampaignRef, datetime]] = field(default_factory=list)
    windows: list[tuple[str, datetime, int]] = field(default_factory=list)

    async def due(self, now: datetime, limit: int) -> list[CampaignRef]:
        self.windows.append(("due", now, limit))
        return self.ready

    async def claim_and_fan_out(self, one: CampaignRef, now: datetime) -> FanOut:
        self.claimed.append((one, now))
        if one.campaign_id in self.poisoned:
            raise NotFound("Sender not found")
        if one.campaign_id in self.lost:
            return FanOut(campaign_id=one.campaign_id, skipped=True)
        return FanOut(campaign_id=one.campaign_id, queued=2, recipients=2)

    async def stuck(self, now: datetime, limit: int) -> list[CampaignRef]:
        self.windows.append(("stuck", now, limit))
        return self.stalled

    async def settle_stuck(self, one: CampaignRef, now: datetime) -> Settled:
        self.settled.append((one, now))
        if one.campaign_id in self.unsettleable:
            raise Upstream("the ledger write failed")
        return Settled(campaign_id=one.campaign_id, missing=1, settled_micro=Micro(42_700))


@dataclass(slots=True)
class FakeWebsites:
    approved: int = 0
    calls: list[datetime] = field(default_factory=list)

    async def approve_due_websites(self, now: datetime) -> int:
        self.calls.append(now)
        return self.approved


def scheduler_over(campaigns: FakeCampaigns, websites: FakeWebsites | None = None) -> Scheduler:
    return Scheduler(campaigns=campaigns, clock=lambda: NOW, websites=websites)


async def test_tick_claims_every_due_campaign() -> None:
    campaigns = FakeCampaigns(ready=[ref("one"), ref("two")])

    await scheduler_over(campaigns).tick()

    assert campaigns.claimed == [(ref("one"), NOW), (ref("two"), NOW)]


async def test_tick_reads_the_due_and_stuck_windows_at_the_page_limit() -> None:
    campaigns = FakeCampaigns()

    await scheduler_over(campaigns).tick()

    assert campaigns.windows == [("due", NOW, DUE_LIMIT), ("stuck", NOW, DUE_LIMIT)]


async def test_tick_carries_on_after_a_lost_claim() -> None:
    campaigns = FakeCampaigns(ready=[ref("one"), ref("two")], lost=frozenset({"one"}))

    await scheduler_over(campaigns).tick()

    assert [one.campaign_id for one, _ in campaigns.claimed] == ["one", "two"]


async def test_tick_settles_every_stuck_campaign() -> None:
    campaigns = FakeCampaigns(stalled=[ref("three")])

    await scheduler_over(campaigns).tick()

    assert campaigns.settled == [(ref("three"), NOW)]


async def test_tick_settles_nothing_when_no_campaign_is_stuck() -> None:
    campaigns = FakeCampaigns(ready=[ref("one")])

    await scheduler_over(campaigns).tick()

    assert campaigns.settled == []


async def test_tick_leaves_websites_alone_when_the_port_is_absent() -> None:
    await scheduler_over(FakeCampaigns()).tick()


async def test_tick_approves_due_websites_when_the_port_is_present() -> None:
    websites = FakeWebsites(approved=2)

    await scheduler_over(FakeCampaigns(), websites).tick()

    assert websites.calls == [NOW]


async def test_tick_fans_out_the_rest_after_a_poisoned_campaign() -> None:
    campaigns = FakeCampaigns(ready=[ref("one"), ref("two")], poisoned=frozenset({"one"}))

    await scheduler_over(campaigns).tick()

    assert [one.campaign_id for one, _ in campaigns.claimed] == ["one", "two"]


async def test_tick_settles_the_stuck_campaigns_after_a_poisoned_campaign() -> None:
    campaigns = FakeCampaigns(
        ready=[ref("one")], stalled=[ref("three")], poisoned=frozenset({"one"})
    )

    await scheduler_over(campaigns).tick()

    assert campaigns.settled == [(ref("three"), NOW)]


async def test_tick_settles_the_rest_after_a_failed_settle() -> None:
    campaigns = FakeCampaigns(
        stalled=[ref("three"), ref("four")], unsettleable=frozenset({"three"})
    )

    await scheduler_over(campaigns).tick()

    assert [one.campaign_id for one, _ in campaigns.settled] == ["three", "four"]


async def test_tick_approves_websites_after_a_poisoned_campaign() -> None:
    campaigns = FakeCampaigns(ready=[ref("one")], poisoned=frozenset({"one"}))
    websites = FakeWebsites(approved=1)

    await scheduler_over(campaigns, websites).tick()

    assert websites.calls == [NOW]

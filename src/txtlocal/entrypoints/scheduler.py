import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from txtlocal.entrypoints import wiring
from txtlocal.shared import runtime, telemetry
from txtlocal.shared.clock import utc_now
from txtlocal.shared.errors import AppError
from txtlocal.slices.campaigns.service import DUE_LIMIT

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock
    from txtlocal.slices.campaigns.model import CampaignRef, FanOut, Settled

CAMPAIGN_ABANDONED = "campaign_abandoned"
CAMPAIGN_FANOUT = "campaign_fanout"
CAMPAIGN_FANOUT_FAILED = "campaign_fanout_failed"
CAMPAIGN_SETTLE_FAILED = "campaign_settle_failed"
SENDERS_DUE_COMPLETED = "senders_due_completed"
TICK_SECONDS = 15
WEBSITES_APPROVED = "websites_approved"


class Campaigns(Protocol):
    async def due(self, now: datetime, limit: int) -> list[CampaignRef]: ...

    async def claim_and_fan_out(self, ref: CampaignRef, now: datetime) -> FanOut: ...

    async def stuck(self, now: datetime, limit: int) -> list[CampaignRef]: ...

    async def settle_stuck(self, ref: CampaignRef, now: datetime) -> Settled: ...


class Websites(Protocol):
    async def approve_due_websites(self, now: datetime) -> int: ...


class SendersDue(Protocol):
    async def run_due_sweep(self, now: datetime) -> int: ...


@dataclass(frozen=True, slots=True)
class Scheduler:
    campaigns: Campaigns
    clock: Clock
    senders: SendersDue | None = None
    websites: Websites | None = None

    async def tick(self) -> None:
        now = self.clock()

        for ref in await self.campaigns.due(now, DUE_LIMIT):
            await self._fan_out(ref, now)

        for ref in await self.campaigns.stuck(now, DUE_LIMIT):
            await self._settle(ref, now)

        if self.websites is not None:
            approved = await self.websites.approve_due_websites(now)
            if approved:
                telemetry.log(WEBSITES_APPROVED, approved=approved)

        if self.senders is not None:
            completed = await self.senders.run_due_sweep(now)
            if completed:
                telemetry.log(SENDERS_DUE_COMPLETED, completed=completed)

    async def _fan_out(self, ref: CampaignRef, now: datetime) -> None:
        try:
            fanned = await self.campaigns.claim_and_fan_out(ref, now)
        except AppError as error:
            telemetry.log(
                CAMPAIGN_FANOUT_FAILED,
                account_id=ref.account_id,
                campaign_id=ref.campaign_id,
                code=error.code,
                level=telemetry.ERROR,
            )
            return

        telemetry.log(
            CAMPAIGN_FANOUT,
            account_id=ref.account_id,
            campaign_id=ref.campaign_id,
            queued=fanned.queued,
            recipients=fanned.recipients,
            skipped=fanned.skipped,
        )

    async def _settle(self, ref: CampaignRef, now: datetime) -> None:
        try:
            settled = await self.campaigns.settle_stuck(ref, now)
        except AppError as error:
            telemetry.log(
                CAMPAIGN_SETTLE_FAILED,
                account_id=ref.account_id,
                campaign_id=ref.campaign_id,
                code=error.code,
                level=telemetry.ERROR,
            )
            return

        telemetry.log(
            CAMPAIGN_ABANDONED,
            account_id=ref.account_id,
            campaign_id=ref.campaign_id,
            missing=settled.missing,
            settled_micro=settled.settled_micro,
            skipped=settled.skipped,
        )


async def ticking(scheduler: Scheduler) -> None:
    while True:
        await scheduler.tick()
        await asyncio.sleep(TICK_SECONDS)


def scheduler() -> Scheduler:
    wiring.register_handlers()
    return Scheduler(
        campaigns=wiring.campaigns(),
        clock=utc_now,
        senders=wiring.senders(),
        websites=wiring.automation(),
    )


def handler(_event: object, _context: object) -> None:
    runtime.run(scheduler().tick())


def main() -> None:
    runtime.run(ticking(scheduler()))


telemetry.configure()

if __name__ == "__main__":
    main()

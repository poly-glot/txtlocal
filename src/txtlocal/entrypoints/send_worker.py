from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from txtlocal.shared import runtime, telemetry
from txtlocal.shared.bus import BatchResponse, SqsEvent, partial_batch
from txtlocal.shared.phone import E164
from txtlocal.slices.messaging.model import Dispatched, DispatchOutcome, SendJob

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock

PREVIEW_CHARS = 80


class Messaging(Protocol):
    async def dispatch(self, job: SendJob, now: datetime) -> Dispatched: ...


class Campaigns(Protocol):
    async def record_outcome(
        self, account_id: str, campaign_id: str, outcome: DispatchOutcome, now: datetime
    ) -> None: ...


class Inbox(Protocol):
    async def note_outbound(
        self, account_id: str, peer: E164, sender_id: str, preview: str, now: datetime
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class SendWorker:
    campaigns: Campaigns
    clock: Clock
    messaging: Messaging
    inbox: Inbox | None = None

    async def handle_body(self, body: str) -> None:
        job = SendJob.model_validate_json(body)
        now = self.clock()

        dispatched = await self.messaging.dispatch(job, now)
        await self.campaigns.record_outcome(
            job.account_id, job.campaign_id, dispatched.outcome, now
        )

        if dispatched.outcome is DispatchOutcome.ACCEPTED and self.inbox is not None:
            await self.inbox.note_outbound(
                job.account_id, E164(job.to), job.sender_id, job.body[:PREVIEW_CHARS], now
            )

        telemetry.log(
            "send_job",
            account_id=job.account_id,
            campaign_id=job.campaign_id,
            message_id=dispatched.message_id,
            outcome=dispatched.outcome,
        )

    async def handle_sqs(self, event: SqsEvent) -> BatchResponse:
        return await partial_batch(event, self.handle_body, "send_job_failed")


from txtlocal.entrypoints import wiring


def handler(event: SqsEvent, _context: object) -> BatchResponse:
    return runtime.run(wiring.send_worker().handle_sqs(event))


telemetry.configure()

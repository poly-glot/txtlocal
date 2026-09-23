from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from txtlocal.entrypoints.send_worker import SendWorker
from txtlocal.shared.bus import LocalBus, Message, Queue, SqsEvent
from txtlocal.shared.errors import AppError, Internal, Upstream
from txtlocal.slices.messaging.model import (
    Dispatched,
    DispatchOutcome,
    MessageType,
    Product,
    SendJob,
)
from txtlocal.slices.messaging.segments import Encoding

ACCOUNT = "account-1"
CAMPAIGN = "campaign-1"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def send_job(to: str) -> SendJob:
    return SendJob(
        account_id=ACCOUNT,
        body="Your code is 123456",
        campaign_id=CAMPAIGN,
        country="GB",
        encoding=Encoding.GSM7,
        message_type=MessageType.TRANSACTIONAL,
        origination="pool-1",
        parts=1,
        price_micro=42_700,
        product=Product.SMS,
        sender_id="sender-1",
        sender_kind="SHARED",
        sender_value="SHARED",
        to=to,
        user_id="user-1",
        username="demo",
    )


def recipients(count: int) -> list[SendJob]:
    return [send_job(f"+4477009001{index:02d}") for index in range(count)]


def sqs_event(jobs: list[SendJob]) -> SqsEvent:
    return {
        "Records": [
            {"body": job.model_dump_json(), "messageId": f"sqs-{index}"}
            for index, job in enumerate(jobs)
        ]
    }


@dataclass(slots=True)
class FakeMessaging:
    dispatched: list[tuple[SendJob, datetime]] = field(default_factory=list)
    failing: dict[str, AppError] = field(default_factory=dict)
    outcomes: dict[str, DispatchOutcome] = field(default_factory=dict)

    async def dispatch(self, job: SendJob, now: datetime) -> Dispatched:
        self.dispatched.append((job, now))

        if (error := self.failing.get(job.to)) is not None:
            raise error

        outcome = self.outcomes.get(job.to, DispatchOutcome.ACCEPTED)
        return Dispatched(message_id=f"message-{job.to}", outcome=outcome)


@dataclass(slots=True)
class FakeCampaigns:
    outcomes: list[tuple[str, str, DispatchOutcome, datetime]] = field(default_factory=list)

    async def record_outcome(
        self, account_id: str, campaign_id: str, outcome: DispatchOutcome, now: datetime
    ) -> None:
        self.outcomes.append((account_id, campaign_id, outcome, now))


@dataclass(slots=True)
class FakeInbox:
    noted: list[tuple[str, str, str, str, datetime]] = field(default_factory=list)

    async def note_outbound(
        self, account_id: str, peer: str, sender_id: str, preview: str, now: datetime
    ) -> None:
        self.noted.append((account_id, peer, sender_id, preview, now))


def worker_over(
    messaging: FakeMessaging, campaigns: FakeCampaigns, inbox: FakeInbox | None = None
) -> SendWorker:
    return SendWorker(campaigns=campaigns, clock=lambda: NOW, messaging=messaging, inbox=inbox)


@pytest.mark.parametrize("outcome", list(DispatchOutcome), ids=["accepted", "duplicate", "refused"])
async def test_handle_body_records_the_dispatch_outcome(outcome: DispatchOutcome) -> None:
    job = send_job("+447700900100")
    messaging = FakeMessaging(outcomes={job.to: outcome})
    campaigns = FakeCampaigns()

    await worker_over(messaging, campaigns).handle_body(job.model_dump_json())

    assert campaigns.outcomes == [(ACCOUNT, CAMPAIGN, outcome, NOW)]


@pytest.mark.parametrize(
    ("outcome", "noted"),
    [
        (
            DispatchOutcome.ACCEPTED,
            [(ACCOUNT, "+447700900100", "sender-1", "Your code is 123456", NOW)],
        ),
        (DispatchOutcome.DUPLICATE, []),
        (DispatchOutcome.REFUSED, []),
    ],
    ids=["accepted-notes-the-inbox", "duplicate-skips-the-inbox", "refused-skips-the-inbox"],
)
async def test_handle_body_notes_outbound_only_on_an_accepted_dispatch(
    outcome: DispatchOutcome, noted: list[tuple[str, str, str, str, datetime]]
) -> None:
    job = send_job("+447700900100")
    messaging = FakeMessaging(outcomes={job.to: outcome})
    inbox = FakeInbox()

    await worker_over(messaging, FakeCampaigns(), inbox).handle_body(job.model_dump_json())

    assert inbox.noted == noted


@pytest.mark.parametrize(
    "error",
    [
        Upstream("SendTextMessage: ServiceUnavailable"),
        Internal("ProvisionedThroughputExceededException"),
    ],
    ids=["gateway-unavailable", "table-throttled"],
)
async def test_handle_sqs_reports_the_failed_job_and_consumes_the_rest(error: AppError) -> None:
    jobs = recipients(10)
    messaging = FakeMessaging(failing={jobs[3].to: error})
    campaigns = FakeCampaigns()

    response = await worker_over(messaging, campaigns).handle_sqs(sqs_event(jobs))

    assert response == {"batchItemFailures": [{"itemIdentifier": "sqs-3"}]}
    assert campaigns.outcomes == [(ACCOUNT, CAMPAIGN, DispatchOutcome.ACCEPTED, NOW)] * 9


async def test_handle_sqs_consumes_a_clean_batch() -> None:
    worker = worker_over(FakeMessaging(), FakeCampaigns())

    response = await worker.handle_sqs(sqs_event(recipients(10)))

    assert response == {"batchItemFailures": []}


async def test_local_bus_round_trip_reaches_the_worker() -> None:
    messaging = FakeMessaging()
    campaigns = FakeCampaigns()
    worker = worker_over(messaging, campaigns)
    bus = LocalBus(handlers={Queue.SEND_JOBS: worker.handle_body}, subscribers={})
    job = send_job("+447700900100")

    await bus.send(Queue.SEND_JOBS, [Message(body=job.model_dump_json())])

    assert messaging.dispatched == [(job, NOW)]
    assert campaigns.outcomes == [(ACCOUNT, CAMPAIGN, DispatchOutcome.ACCEPTED, NOW)]


async def test_handle_sqs_fails_only_the_record_that_is_not_a_send_job() -> None:
    event = sqs_event(recipients(3))
    event["Records"][1]["body"] = "{"
    campaigns = FakeCampaigns()

    response = await worker_over(FakeMessaging(), campaigns).handle_sqs(event)

    assert response == {"batchItemFailures": [{"itemIdentifier": "sqs-1"}]}


async def test_handle_sqs_dispatches_the_records_around_a_malformed_body() -> None:
    event = sqs_event(recipients(3))
    event["Records"][1]["body"] = "{"
    messaging = FakeMessaging()

    await worker_over(messaging, FakeCampaigns()).handle_sqs(event)

    assert [job.to for job, _ in messaging.dispatched] == ["+447700900100", "+447700900102"]

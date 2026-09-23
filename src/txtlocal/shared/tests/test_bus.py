from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Unpack, cast

import pytest

from txtlocal.shared.bus import (
    Bus,
    LocalBus,
    Message,
    Queue,
    SqsBus,
    SqsEvent,
    Topic,
    failure_code,
    partial_batch,
)
from txtlocal.shared.errors import UPSTREAM_MESSAGE, Upstream
from txtlocal.shared.testing import RecordingBus

if TYPE_CHECKING:
    from types_aiobotocore_sns import SNSClient
    from types_aiobotocore_sns.type_defs import PublishInputTypeDef, PublishResponseTypeDef
    from types_aiobotocore_sqs import SQSClient
    from types_aiobotocore_sqs.type_defs import (
        ResponseMetadataTypeDef,
        SendMessageBatchRequestEntryTypeDef,
        SendMessageBatchRequestTypeDef,
        SendMessageBatchResultTypeDef,
    )

QUEUE_URL = "https://sqs.eu-west-2.amazonaws.com/123456789012/send-jobs"
TOPIC_ARN = "arn:aws:sns:eu-west-2:123456789012:sms-events"
POISON = "not-json"
REFUSED = "refused"
RESPONSE_METADATA: ResponseMetadataTypeDef = {
    "HTTPHeaders": {},
    "HTTPStatusCode": 200,
    "RequestId": "request",
    "RetryAttempts": 0,
}


@dataclass(slots=True)
class Recorder:
    bodies: list[str] = field(default_factory=list)

    async def handle(self, body: str) -> None:
        self.bodies.append(body)


@dataclass(slots=True)
class FakeSqs:
    batches: list[tuple[str, Sequence[SendMessageBatchRequestEntryTypeDef]]] = field(
        default_factory=list
    )
    failing_ids: frozenset[str] = field(default_factory=frozenset)

    async def send_message_batch(
        self, **kwargs: Unpack[SendMessageBatchRequestTypeDef]
    ) -> SendMessageBatchResultTypeDef:
        entries = kwargs["Entries"]
        self.batches.append((kwargs["QueueUrl"], entries))

        failed = [entry["Id"] for entry in entries if entry["Id"] in self.failing_ids]
        successful = [entry["Id"] for entry in entries if entry["Id"] not in self.failing_ids]
        return {
            "Failed": [
                {"Code": "ServiceUnavailable", "Id": ident, "SenderFault": False}
                for ident in failed
            ],
            "ResponseMetadata": RESPONSE_METADATA,
            "Successful": [
                {"Id": ident, "MD5OfMessageBody": "", "MessageId": ident} for ident in successful
            ],
        }


@dataclass(slots=True)
class FakeSns:
    published: list[tuple[str, str]] = field(default_factory=list)

    async def publish(self, **kwargs: Unpack[PublishInputTypeDef]) -> PublishResponseTypeDef:
        self.published.append((kwargs["TopicArn"], kwargs["Message"]))
        return {
            "MessageId": "message",
            "ResponseMetadata": RESPONSE_METADATA,
            "SequenceNumber": "1",
        }


def bus_over(sqs: FakeSqs, sns: FakeSns) -> SqsBus:
    return SqsBus(
        queue_urls={Queue.SEND_JOBS: QUEUE_URL},
        sns=cast("SNSClient", sns),
        sqs=cast("SQSClient", sqs),
        topic_arns={Topic.SMS_EVENTS: TOPIC_ARN},
    )


def jobs(count: int) -> list[Message]:
    return [Message(body=f"job-{index}") for index in range(count)]


def sqs_event(bodies: Sequence[str]) -> SqsEvent:
    return {
        "Records": [
            {"body": body, "messageId": f"sqs-{index}"} for index, body in enumerate(bodies)
        ]
    }


@dataclass(slots=True)
class Fussy:
    handled: list[str] = field(default_factory=list)

    async def handle(self, body: str) -> None:
        if body == POISON:
            raise ValueError(body)
        if body == REFUSED:
            raise Upstream(body)

        self.handled.append(body)


async def test_local_bus_awaits_the_handler_per_message_in_order() -> None:
    recorder = Recorder()
    bus: Bus = LocalBus(handlers={Queue.SEND_JOBS: recorder.handle}, subscribers={})

    await bus.send(Queue.SEND_JOBS, jobs(3))

    assert recorder.bodies == ["job-0", "job-1", "job-2"]


async def test_local_bus_awaits_the_subscriber_on_publish() -> None:
    recorder = Recorder()
    bus = LocalBus(handlers={}, subscribers={Topic.SMS_EVENTS: recorder.handle})

    await bus.publish(Topic.SMS_EVENTS, "event")

    assert recorder.bodies == ["event"]


async def test_local_bus_refuses_a_queue_without_a_handler() -> None:
    bus = LocalBus(handlers={}, subscribers={})

    with pytest.raises(KeyError):
        await bus.send(Queue.WEBHOOKS, jobs(1))


@pytest.mark.parametrize(
    ("count", "batch_sizes"),
    [(10, [10]), (11, [10, 1]), (25, [10, 10, 5])],
    ids=["ten-is-one-batch", "eleven-spills-into-two", "twenty-five-is-three"],
)
async def test_sqs_bus_sends_in_batches_of_ten_numbered_from_zero(
    count: int, batch_sizes: list[int]
) -> None:
    sqs = FakeSqs()

    await bus_over(sqs, FakeSns()).send(Queue.SEND_JOBS, jobs(count))

    ids = [[entry["Id"] for entry in entries] for _, entries in sqs.batches]
    assert ids == [[str(index) for index in range(size)] for size in batch_sizes]


async def test_sqs_bus_entry_carries_the_body_and_delay_to_the_queue_url() -> None:
    sqs = FakeSqs()

    await bus_over(sqs, FakeSns()).send(Queue.SEND_JOBS, [Message(body="job", delay_seconds=30)])

    assert sqs.batches == [(QUEUE_URL, [{"DelaySeconds": 30, "Id": "0", "MessageBody": "job"}])]


async def test_sqs_bus_raises_upstream_when_an_entry_fails() -> None:
    sqs = FakeSqs(failing_ids=frozenset({"3"}))

    with pytest.raises(Upstream) as caught:
        await bus_over(sqs, FakeSns()).send(Queue.SEND_JOBS, jobs(10))

    assert str(caught.value) == "SendMessageBatch to send-jobs: 1 of 10 failed: ServiceUnavailable"
    assert caught.value.public_message() == UPSTREAM_MESSAGE


async def test_sqs_bus_publishes_to_the_topic_arn() -> None:
    sns = FakeSns()
    bus: Bus = bus_over(FakeSqs(), sns)

    await bus.publish(Topic.SMS_EVENTS, "event")

    assert sns.published == [(TOPIC_ARN, "event")]


async def test_recording_bus_records_each_call() -> None:
    recording = RecordingBus()
    bus: Bus = recording

    await bus.send(Queue.SEND_JOBS, jobs(2))
    await bus.publish(Topic.SMS_EVENTS, "event")

    assert recording.sent == [(Queue.SEND_JOBS, jobs(2))]
    assert recording.published == [(Topic.SMS_EVENTS, "event")]


@pytest.mark.parametrize(
    ("error", "code"),
    [(Upstream("gone"), "upstream"), (ValueError("not-json"), "ValueError")],
    ids=["an-app-error-carries-its-code", "a-value-error-carries-its-class-name"],
)
def test_failure_code(error: Exception, code: str) -> None:
    assert failure_code(error) == code


@pytest.mark.parametrize(
    "body", [POISON, REFUSED], ids=["a-malformed-body", "an-application-error"]
)
async def test_partial_batch_reports_only_the_failing_record(body: str) -> None:
    fussy = Fussy()

    response = await partial_batch(sqs_event(["job-0", body, "job-2"]), fussy.handle, "failed")

    assert response == {"batchItemFailures": [{"itemIdentifier": "sqs-1"}]}


async def test_partial_batch_consumes_the_records_around_a_malformed_body() -> None:
    fussy = Fussy()

    await partial_batch(sqs_event(["job-0", POISON, "job-2"]), fussy.handle, "failed")

    assert fussy.handled == ["job-0", "job-2"]

import itertools
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, TypedDict

from txtlocal.shared import telemetry
from txtlocal.shared.errors import AppError, Upstream

if TYPE_CHECKING:
    from types_aiobotocore_sns import SNSClient
    from types_aiobotocore_sqs import SQSClient
    from types_aiobotocore_sqs.type_defs import SendMessageBatchRequestEntryTypeDef

SQS_BATCH_SIZE = 10


class SqsRecord(TypedDict):
    body: str
    messageId: str


class SqsEvent(TypedDict):
    Records: list[SqsRecord]


class ItemFailure(TypedDict):
    itemIdentifier: str


class BatchResponse(TypedDict):
    batchItemFailures: list[ItemFailure]


def failure_code(error: Exception) -> str:
    return error.code if isinstance(error, AppError) else type(error).__name__


async def partial_batch(
    event: SqsEvent, handle: Callable[[str], Awaitable[None]], failed_event: str
) -> BatchResponse:
    failures: list[ItemFailure] = []
    for record in event["Records"]:
        try:
            await handle(record["body"])
        except (AppError, ValueError) as error:
            telemetry.log(
                failed_event,
                code=failure_code(error),
                item_identifier=record["messageId"],
                level=telemetry.ERROR,
            )
            failures.append({"itemIdentifier": record["messageId"]})

    return {"batchItemFailures": failures}


class Queue(StrEnum):
    RECHARGE = "recharge"
    SEND_JOBS = "send-jobs"
    WEBHOOKS = "webhooks"


class Topic(StrEnum):
    SMS_EVENTS = "sms-events"
    SMS_INBOUND = "sms-inbound"


@dataclass(frozen=True, slots=True)
class Message:
    body: str
    delay_seconds: int = 0


type Handler = Callable[[str], Awaitable[None]]


class Bus(Protocol):
    async def send(self, queue: Queue, messages: Sequence[Message]) -> None: ...

    async def publish(self, topic: Topic, body: str) -> None: ...


@dataclass(frozen=True, slots=True)
class LocalBus:
    handlers: Mapping[Queue, Handler]
    subscribers: Mapping[Topic, Handler]

    async def send(self, queue: Queue, messages: Sequence[Message]) -> None:
        handler = self.handlers[queue]

        for message in messages:
            await handler(message.body)

    async def publish(self, topic: Topic, body: str) -> None:
        await self.subscribers[topic](body)


def batch_entry(index: int, message: Message) -> SendMessageBatchRequestEntryTypeDef:
    return {"DelaySeconds": message.delay_seconds, "Id": str(index), "MessageBody": message.body}


@dataclass(frozen=True, slots=True)
class SqsBus:
    queue_urls: Mapping[Queue, str]
    sns: SNSClient
    sqs: SQSClient
    topic_arns: Mapping[Topic, str]

    async def send(self, queue: Queue, messages: Sequence[Message]) -> None:
        queue_url = self.queue_urls[queue]

        for batch in itertools.batched(messages, SQS_BATCH_SIZE, strict=False):
            entries = [batch_entry(index, message) for index, message in enumerate(batch)]
            response = await self.sqs.send_message_batch(Entries=entries, QueueUrl=queue_url)

            if failed := response["Failed"]:
                codes = ", ".join(sorted({entry["Code"] for entry in failed}))
                raise Upstream(
                    f"SendMessageBatch to {queue}: {len(failed)} of {len(batch)} failed: {codes}"
                )

    async def publish(self, topic: Topic, body: str) -> None:
        await self.sns.publish(Message=body, TopicArn=self.topic_arns[topic])

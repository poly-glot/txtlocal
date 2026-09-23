import os
import secrets
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import aioboto3
import pytest

from txtlocal.shared.table import Table

if TYPE_CHECKING:
    from txtlocal.shared.bus import Message, Queue, Topic

SKIP_NOTICE = "AWS_ENDPOINT_URL_DYNAMODB is unset; DynamoDB Local integration tests are skipped"


@asynccontextmanager
async def local_repo_table(prefix: str) -> AsyncIterator[Table]:
    endpoint = os.environ.get("AWS_ENDPOINT_URL_DYNAMODB")
    if endpoint is None:
        pytest.skip(SKIP_NOTICE)

    name = f"{prefix}-run_{secrets.token_hex(6)}"
    region = os.environ.get("AWS_REGION")
    async with aioboto3.Session().client(
        "dynamodb", endpoint_url=endpoint, region_name=region
    ) as client:
        await client.create_table(
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
                {"AttributeName": "GSI1PK", "AttributeType": "S"},
                {"AttributeName": "GSI1SK", "AttributeType": "S"},
                {"AttributeName": "GSI2PK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "GSI1",
                    "KeySchema": [
                        {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                        {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                },
                {
                    "IndexName": "GSI2",
                    "KeySchema": [{"AttributeName": "GSI2PK", "KeyType": "HASH"}],
                    "Projection": {"ProjectionType": "ALL"},
                },
            ],
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            TableName=name,
        )
        await client.get_waiter("table_exists").wait(TableName=name)

        yield Table(client=client, name=name)

        await client.delete_table(TableName=name)


@dataclass(frozen=True, slots=True)
class RecordingBus:
    published: list[tuple[Topic, str]] = field(default_factory=list)
    sent: list[tuple[Queue, list[Message]]] = field(default_factory=list)

    async def send(self, queue: Queue, messages: Sequence[Message]) -> None:
        self.sent.append((queue, list(messages)))

    async def publish(self, topic: Topic, body: str) -> None:
        self.published.append((topic, body))

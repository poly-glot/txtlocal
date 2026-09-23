import asyncio
import itertools
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from txtlocal.shared.errors import Internal
from txtlocal.shared.model import model_of
from txtlocal.shared.table import (
    IF_PRESENT,
    Table,
    condition_failed_as_false,
    key,
    n,
    paged_items,
    partition,
    s,
    sort_ts,
)
from txtlocal.slices.billing.model import Page
from txtlocal.slices.inbox.model import Conversation, ConversationStatus
from txtlocal.slices.messaging.model import Direction

if TYPE_CHECKING:
    from types_aiobotocore_dynamodb.type_defs import AttributeValueTypeDef, QueryInputTypeDef

    from txtlocal.shared.phone import E164

ACCOUNT = "ACCOUNT"
CONCURRENCY = 10
CONV_PREFIX = "CONV#"
CONV_SUFFIX = "#CONV"
CURSOR_SEPARATOR = "#"
LISTING_INDEX = "GSI1"
PAGE_CAP = 12
PAGE_CAP_EXCEEDED = "conversations exceeded the page cap"

BY_LISTING = "GSI1PK = :pk"
MARK_READ = "SET unread = :zero"
SET_STATUS = "SET #status = :status"
STATUS_FILTER = "#status = :status"
STATUS_NAME = {"#status": "status"}
UNREAD_FILTER = "unread > :zero"
UPSERT_INBOUND = (
    "SET GSI1PK = :gsi1pk, GSI1SK = :lastAt, lastAt = :lastAt, lastDirection = :direction, "
    "lastPreview = :preview, peer = :peer, #status = :open ADD unread :one"
)
UPSERT_INBOUND_WITH_SENDER = (
    "SET GSI1PK = :gsi1pk, GSI1SK = :lastAt, lastAt = :lastAt, lastDirection = :direction, "
    "lastPreview = :preview, lastSenderId = :senderId, peer = :peer, #status = :open "
    "ADD unread :one"
)
UPSERT_OUTBOUND = (
    "SET GSI1PK = :gsi1pk, GSI1SK = :lastAt, lastAt = :lastAt, lastDirection = :direction, "
    "lastPreview = :preview, lastSenderId = :senderId, peer = :peer"
)


class InboxRepo(Protocol):
    async def get(self, account_id: str, peer: E164) -> Conversation | None: ...

    async def list_conversations(
        self,
        account_id: str,
        status: ConversationStatus | None,
        cursor: str | None,
        limit: int,
    ) -> Page[Conversation]: ...

    async def mark_all_read(self, account_id: str) -> None: ...

    async def mark_read(self, account_id: str, peer: E164) -> bool: ...

    async def set_status(self, account_id: str, peer: E164, status: ConversationStatus) -> bool: ...

    async def upsert_inbound(
        self, account_id: str, peer: E164, preview: str, sender_id: str | None, now: datetime
    ) -> None: ...

    async def upsert_outbound(
        self, account_id: str, peer: E164, preview: str, sender_id: str, now: datetime
    ) -> None: ...


def conversation_key(account_id: str, peer: E164) -> dict[str, AttributeValueTypeDef]:
    return key(partition(ACCOUNT, account_id), f"{CONV_PREFIX}{peer}")


def listing_partition(account_id: str) -> str:
    return partition(ACCOUNT, f"{account_id}{CONV_SUFFIX}")


def cursor_of(conversation: Conversation) -> str:
    return f"{sort_ts(conversation.last_at)}{CURSOR_SEPARATOR}{conversation.peer}"


def resume_key(account_id: str, cursor: str) -> dict[str, AttributeValueTypeDef] | None:
    last_at, separator, peer = cursor.partition(CURSOR_SEPARATOR)
    if not (separator and last_at and peer):
        return None

    return {
        "GSI1PK": s(listing_partition(account_id)),
        "GSI1SK": s(last_at),
        "PK": s(partition(ACCOUNT, account_id)),
        "SK": s(f"{CONV_PREFIX}{peer}"),
    }


def listing_request(
    table_name: str,
    account_id: str,
    status: ConversationStatus | None,
    cursor: str | None,
    limit: int,
) -> QueryInputTypeDef:
    values: dict[str, AttributeValueTypeDef] = {":pk": s(listing_partition(account_id))}
    request: QueryInputTypeDef = {
        "ExpressionAttributeValues": values,
        "IndexName": LISTING_INDEX,
        "KeyConditionExpression": BY_LISTING,
        "Limit": limit,
        "ScanIndexForward": False,
        "TableName": table_name,
    }

    if status is not None:
        values[":status"] = s(status)
        request["ExpressionAttributeNames"] = STATUS_NAME
        request["FilterExpression"] = STATUS_FILTER

    if cursor is not None:
        resumed = resume_key(account_id, cursor)
        if resumed is not None:
            request["ExclusiveStartKey"] = resumed

    return request


def page_of(conversations: Sequence[Conversation], limit: int, *, more: bool) -> Page[Conversation]:
    wanted = list(conversations[:limit])
    resumable = bool(wanted) and (more or len(conversations) > limit)
    return Page[Conversation](
        items=wanted, next_cursor=cursor_of(wanted[-1]) if resumable else None
    )


@dataclass(frozen=True, slots=True)
class InboxDynamoRepo:
    table: Table

    async def get(self, account_id: str, peer: E164) -> Conversation | None:
        response = await self.table.client.get_item(
            Key=conversation_key(account_id, peer), TableName=self.table.name
        )
        item = response.get("Item")
        return model_of(Conversation, item) if item else None

    async def list_conversations(
        self,
        account_id: str,
        status: ConversationStatus | None,
        cursor: str | None,
        limit: int,
    ) -> Page[Conversation]:
        request = listing_request(self.table.name, account_id, status, cursor, limit)

        found: list[Conversation] = []
        for _ in range(PAGE_CAP):
            response = await self.table.client.query(**request)
            found.extend(model_of(Conversation, item) for item in response.get("Items", []))

            last_key = response.get("LastEvaluatedKey")
            if len(found) >= limit or not last_key:
                return page_of(found, limit, more=bool(last_key))

            request["ExclusiveStartKey"] = last_key

        raise Internal(PAGE_CAP_EXCEEDED)

    async def mark_all_read(self, account_id: str) -> None:
        request: QueryInputTypeDef = {
            "ExpressionAttributeValues": {":pk": s(listing_partition(account_id)), ":zero": n(0)},
            "FilterExpression": UNREAD_FILTER,
            "IndexName": LISTING_INDEX,
            "KeyConditionExpression": BY_LISTING,
            "TableName": self.table.name,
        }

        items = await paged_items(self.table.client, request, PAGE_CAP, PAGE_CAP_EXCEEDED)
        conversations = [model_of(Conversation, item) for item in items]
        for chunk in itertools.batched(conversations, CONCURRENCY, strict=False):
            await asyncio.gather(*(self._zero_unread(account_id, one.peer) for one in chunk))

    async def mark_read(self, account_id: str, peer: E164) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeValues={":zero": n(0)},
            Key=conversation_key(account_id, peer),
            TableName=self.table.name,
            UpdateExpression=MARK_READ,
        )

    async def set_status(self, account_id: str, peer: E164, status: ConversationStatus) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeNames=STATUS_NAME,
            ExpressionAttributeValues={":status": s(status)},
            Key=conversation_key(account_id, peer),
            TableName=self.table.name,
            UpdateExpression=SET_STATUS,
        )

    async def upsert_inbound(
        self, account_id: str, peer: E164, preview: str, sender_id: str | None, now: datetime
    ) -> None:
        values: dict[str, AttributeValueTypeDef] = {
            ":direction": s(Direction.IN),
            ":gsi1pk": s(listing_partition(account_id)),
            ":lastAt": s(sort_ts(now)),
            ":one": n(1),
            ":open": s(ConversationStatus.OPEN),
            ":peer": s(peer),
            ":preview": s(preview),
        }
        expression = UPSERT_INBOUND
        if sender_id is not None:
            values[":senderId"] = s(sender_id)
            expression = UPSERT_INBOUND_WITH_SENDER

        await self.table.client.update_item(
            ExpressionAttributeNames=STATUS_NAME,
            ExpressionAttributeValues=values,
            Key=conversation_key(account_id, peer),
            TableName=self.table.name,
            UpdateExpression=expression,
        )

    async def upsert_outbound(
        self, account_id: str, peer: E164, preview: str, sender_id: str, now: datetime
    ) -> None:
        await self.table.client.update_item(
            ExpressionAttributeValues={
                ":direction": s(Direction.OUT),
                ":gsi1pk": s(listing_partition(account_id)),
                ":lastAt": s(sort_ts(now)),
                ":peer": s(peer),
                ":preview": s(preview),
                ":senderId": s(sender_id),
            },
            Key=conversation_key(account_id, peer),
            TableName=self.table.name,
            UpdateExpression=UPSERT_OUTBOUND,
        )

    async def _zero_unread(self, account_id: str, peer: E164) -> None:
        await self.table.client.update_item(
            ExpressionAttributeValues={":zero": n(0)},
            Key=conversation_key(account_id, peer),
            TableName=self.table.name,
            UpdateExpression=MARK_READ,
        )

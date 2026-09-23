from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from txtlocal.shared.errors import Internal
from txtlocal.shared.model import get_model, model_of
from txtlocal.shared.table import (
    IF_PRESENT,
    UNSUPPORTED_ATTRIBUTE,
    Table,
    condition_failed_as_false,
    delete_if_present,
    key,
    n,
    paged_items,
    partition,
    prefix_items,
    s,
    sort_ts,
)
from txtlocal.slices.senders.model import Sender, SenderKind, SenderStatus, SmartSender

if TYPE_CHECKING:
    from types_aiobotocore_dynamodb.type_defs import (
        AttributeValueTypeDef,
        QueryInputTypeDef,
        TransactWriteItemTypeDef,
    )

    from txtlocal.shared.model import Model

ACCOUNT = "ACCOUNT"
ACCOUNT_PREFIX = partition(ACCOUNT, "")
ALPHA_UNDER_REVIEW_PARTITION = partition("ALPHA", "UNDER_REVIEW")
GSI2 = "GSI2"
PAGE_CAP = 4
PAGE_CAP_EXCEEDED = "senders exceeded the page cap"
RENTED_PARTITION = partition("SENDERS", "RENTED")
SENDER_PREFIX = "SENDER#"
SMART_PREFIX = "SMART#"

BY_GSI2 = "GSI2PK = :pk"
CANCEL_RENTAL = "SET cancelled = :true"
COMPLETE_ALPHA_TAG = "SET #status = :status REMOVE GSI2PK"
IF_ABSENT = "attribute_not_exists(PK)"
IF_POINTING_AT = "senderId = :current"
MARK_VERIFIED = "SET #status = :status, verifiedAt = :verifiedAt"
RECORD_RENEWAL = "SET renewsAt = :renewsAt, renewalAttempt = :zero"
RECORD_RENEWAL_ATTEMPT = "ADD renewalAttempt :one"
RELEASE_SENDER = "SET #status = :status REMOVE GSI2PK"
STATUS_NAME = {"#status": "status"}


class SendersRepo(Protocol):
    async def alpha_tags_under_review(self) -> list[tuple[str, Sender]]: ...

    async def cancel_rental(self, account_id: str, sender_id: str) -> bool: ...

    async def complete_alpha_tag(
        self, account_id: str, sender_id: str, status: SenderStatus
    ) -> bool: ...

    async def delete_sender(self, account_id: str, sender_id: str) -> bool: ...

    async def get_sender(self, account_id: str, sender_id: str) -> Sender | None: ...

    async def list_senders(self, account_id: str) -> list[Sender]: ...

    async def list_smart(self, account_id: str) -> list[SmartSender]: ...

    async def mark_verified(self, account_id: str, sender_id: str, now: datetime) -> bool: ...

    async def put_defaults_if_absent(
        self, account_id: str, sender: Sender, smart: SmartSender
    ) -> bool: ...

    async def put_sender(self, account_id: str, sender: Sender) -> None: ...

    async def record_renewal(
        self, account_id: str, sender_id: str, renews_at: datetime
    ) -> bool: ...

    async def record_renewal_attempt(self, account_id: str, sender_id: str) -> bool: ...

    async def release(self, account_id: str, sender_id: str) -> bool: ...

    async def rented_numbers(self) -> list[tuple[str, Sender]]: ...

    async def replace_smart_if_pointing_at(
        self, account_id: str, smart: SmartSender, current: str
    ) -> bool: ...

    async def set_smart(self, account_id: str, smart: SmartSender) -> None: ...


def sender_key(account_id: str, sender_id: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(ACCOUNT, account_id), f"{SENDER_PREFIX}{sender_id}")


def smart_key(account_id: str, country: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(ACCOUNT, account_id), f"{SMART_PREFIX}{country}")


def attribute(value: object) -> AttributeValueTypeDef:
    match value:
        case bool():
            return {"BOOL": value}
        case int():
            return {"N": str(value)}
        case str():
            return {"S": value}
        case list():
            return {"L": [attribute(entry) for entry in value]}
    raise Internal(UNSUPPORTED_ATTRIBUTE)


def item_of(
    model: Model, item_key: dict[str, AttributeValueTypeDef]
) -> dict[str, AttributeValueTypeDef]:
    fields = model.model_dump(exclude_none=True, mode="json")
    return item_key | {name: attribute(value) for name, value in fields.items()}


def pk_of(item: Mapping[str, AttributeValueTypeDef]) -> str:
    match item["PK"]:
        case {"S": str(text)}:
            return text
    raise Internal(UNSUPPORTED_ATTRIBUTE)


def account_id_of(item: Mapping[str, AttributeValueTypeDef]) -> str:
    return pk_of(item).removeprefix(ACCOUNT_PREFIX)


def sender_item(account_id: str, sender: Sender) -> dict[str, AttributeValueTypeDef]:
    item = item_of(sender, sender_key(account_id, sender.sender_id))
    if sender.kind is SenderKind.DEDICATED and sender.status is not SenderStatus.RELEASED:
        return item | {"GSI2PK": s(RENTED_PARTITION)}
    if sender.kind is SenderKind.ALPHA and sender.status is SenderStatus.UNDER_REVIEW:
        return item | {"GSI2PK": s(ALPHA_UNDER_REVIEW_PARTITION)}
    return item


@dataclass(frozen=True, slots=True)
class SendersDynamoRepo:
    table: Table

    async def alpha_tags_under_review(self) -> list[tuple[str, Sender]]:
        request: QueryInputTypeDef = {
            "ExpressionAttributeValues": {":pk": s(ALPHA_UNDER_REVIEW_PARTITION)},
            "IndexName": GSI2,
            "KeyConditionExpression": BY_GSI2,
            "TableName": self.table.name,
        }
        items = await self._paged(request)
        return [(account_id_of(item), model_of(Sender, item)) for item in items]

    async def cancel_rental(self, account_id: str, sender_id: str) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeValues={":true": {"BOOL": True}},
            Key=sender_key(account_id, sender_id),
            TableName=self.table.name,
            UpdateExpression=CANCEL_RENTAL,
        )

    async def complete_alpha_tag(
        self, account_id: str, sender_id: str, status: SenderStatus
    ) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeNames=STATUS_NAME,
            ExpressionAttributeValues={":status": s(status)},
            Key=sender_key(account_id, sender_id),
            TableName=self.table.name,
            UpdateExpression=COMPLETE_ALPHA_TAG,
        )

    async def delete_sender(self, account_id: str, sender_id: str) -> bool:
        return await delete_if_present(self.table, sender_key(account_id, sender_id))

    async def get_sender(self, account_id: str, sender_id: str) -> Sender | None:
        return await get_model(self.table, Sender, sender_key(account_id, sender_id))

    async def list_senders(self, account_id: str) -> list[Sender]:
        return [model_of(Sender, item) for item in await self._query(account_id, SENDER_PREFIX)]

    async def list_smart(self, account_id: str) -> list[SmartSender]:
        return [model_of(SmartSender, item) for item in await self._query(account_id, SMART_PREFIX)]

    async def mark_verified(self, account_id: str, sender_id: str, now: datetime) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeNames=STATUS_NAME,
            ExpressionAttributeValues={
                ":status": s(SenderStatus.READY),
                ":verifiedAt": s(sort_ts(now)),
            },
            Key=sender_key(account_id, sender_id),
            TableName=self.table.name,
            UpdateExpression=MARK_VERIFIED,
        )

    async def put_defaults_if_absent(
        self, account_id: str, sender: Sender, smart: SmartSender
    ) -> bool:
        return await condition_failed_as_false(self.table.client.transact_write_items)(
            TransactItems=[
                self._put_if_absent(sender_item(account_id, sender)),
                self._put_if_absent(item_of(smart, smart_key(account_id, smart.country))),
            ]
        )

    async def put_sender(self, account_id: str, sender: Sender) -> None:
        await condition_failed_as_false(self.table.client.put_item)(
            Item=sender_item(account_id, sender),
            TableName=self.table.name,
        )

    async def record_renewal(self, account_id: str, sender_id: str, renews_at: datetime) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeValues={":renewsAt": s(sort_ts(renews_at)), ":zero": n(0)},
            Key=sender_key(account_id, sender_id),
            TableName=self.table.name,
            UpdateExpression=RECORD_RENEWAL,
        )

    async def record_renewal_attempt(self, account_id: str, sender_id: str) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeValues={":one": n(1)},
            Key=sender_key(account_id, sender_id),
            TableName=self.table.name,
            UpdateExpression=RECORD_RENEWAL_ATTEMPT,
        )

    async def release(self, account_id: str, sender_id: str) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeNames=STATUS_NAME,
            ExpressionAttributeValues={":status": s(SenderStatus.RELEASED)},
            Key=sender_key(account_id, sender_id),
            TableName=self.table.name,
            UpdateExpression=RELEASE_SENDER,
        )

    async def rented_numbers(self) -> list[tuple[str, Sender]]:
        request: QueryInputTypeDef = {
            "ExpressionAttributeValues": {":pk": s(RENTED_PARTITION)},
            "IndexName": GSI2,
            "KeyConditionExpression": BY_GSI2,
            "TableName": self.table.name,
        }
        items = await self._paged(request)
        return [(account_id_of(item), model_of(Sender, item)) for item in items]

    async def replace_smart_if_pointing_at(
        self, account_id: str, smart: SmartSender, current: str
    ) -> bool:
        return await condition_failed_as_false(self.table.client.put_item)(
            ConditionExpression=IF_POINTING_AT,
            ExpressionAttributeValues={":current": s(current)},
            Item=item_of(smart, smart_key(account_id, smart.country)),
            TableName=self.table.name,
        )

    async def set_smart(self, account_id: str, smart: SmartSender) -> None:
        await condition_failed_as_false(self.table.client.put_item)(
            Item=item_of(smart, smart_key(account_id, smart.country)),
            TableName=self.table.name,
        )

    def _put_if_absent(self, item: dict[str, AttributeValueTypeDef]) -> TransactWriteItemTypeDef:
        return {
            "Put": {"ConditionExpression": IF_ABSENT, "Item": item, "TableName": self.table.name}
        }

    async def _query(self, account_id: str, prefix: str) -> list[dict[str, AttributeValueTypeDef]]:
        return await prefix_items(
            self.table, partition(ACCOUNT, account_id), prefix, PAGE_CAP, PAGE_CAP_EXCEEDED
        )

    async def _paged(self, request: QueryInputTypeDef) -> list[dict[str, AttributeValueTypeDef]]:
        return await paged_items(self.table.client, request, PAGE_CAP, PAGE_CAP_EXCEEDED)

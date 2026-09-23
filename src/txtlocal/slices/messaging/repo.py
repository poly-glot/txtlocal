from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import TYPE_CHECKING, Protocol, assert_never

from txtlocal.shared.errors import Internal
from txtlocal.shared.table import (
    IF_PRESENT,
    METADATA_SK,
    Table,
    condition_failed_as_false,
    key,
    n,
    paged_items,
    partition,
    s,
    sort_ts,
)
from txtlocal.slices.messaging.model import (
    DeliveryUpdate,
    MessageKey,
    MessageRow,
    MessageStatus,
    Product,
    SearchField,
    Template,
    message_key_for,
    message_partition,
    minted_at,
)

if TYPE_CHECKING:
    from types_aiobotocore_dynamodb.type_defs import (
        AttributeValueTypeDef,
        QueryInputTypeDef,
        UpdateItemInputTypeDef,
    )

    from txtlocal.shared.model import Model
    from txtlocal.shared.phone import E164

MESSAGE_TTL = timedelta(days=120)
MARKER_TTL = timedelta(days=2)
CAP_TTL = timedelta(days=2)
MAX_QUERY_PAGES = 10
TEMPLATE_PREFIX = "TEMPLATE#"
INBOUND_MARKER_PREFIX = "INBOUND#"
COUNTER_LOST = "the daily cap counter returned nothing"
TEMPLATES_UNBOUNDED = "an account holds more templates than the page cap reads"

GSI1 = "GSI1"
GSI2 = "GSI2"

CLAIM_ATTEMPT = "SET attemptedAt = :at"
IF_ABSENT = "attribute_not_exists(PK)"
IF_QUEUED = "#status = :queued"
IF_NOT_FINAL = "#status IN (:queued, :sent)"
IF_UNATTEMPTED = "#status = :queued AND attribute_not_exists(attemptedAt)"
MARK_SENT = (
    "SET #status = :status, providerMessageId = :providerMessageId, sentAt = :at, GSI2PK = :gsi2pk"
)
REFUSE = "SET #status = :status, failureReason = :failureReason"
RECORD_SENT = (
    "SET #status = :status, "
    "providerMessageId = if_not_exists(providerMessageId, :providerMessageId), "
    "sentAt = if_not_exists(sentAt, :at), "
    "GSI2PK = if_not_exists(GSI2PK, :gsi2pk)"
)
RECORD_DELIVERED = (
    "SET #status = :status, deliveredAt = :at, "
    "providerMessageId = if_not_exists(providerMessageId, :providerMessageId), "
    "sentAt = if_not_exists(sentAt, :at), "
    "GSI2PK = if_not_exists(GSI2PK, :gsi2pk)"
)
RECORD_FAILED = (
    "SET #status = :status, failureReason = :failureReason, "
    "providerMessageId = if_not_exists(providerMessageId, :providerMessageId), "
    "sentAt = if_not_exists(sentAt, :at), "
    "GSI2PK = if_not_exists(GSI2PK, :gsi2pk)"
)
COUNT_SEND = "ADD n :one SET #ttl = if_not_exists(#ttl, :ttl)"
EDIT_TEMPLATE = "SET #name = :name, body = :body"
HISTORY_KEYS = "PK = :pk AND SK BETWEEN :since AND :until"
NUMBER_FILTER = "#field = :number"
KIND_FILTER = "begins_with(kind, :kind)"
TEMPLATE_KEYS = "PK = :pk AND begins_with(SK, :prefix)"
CONVERSATION_KEYS = "GSI1PK = :pk"
PROVIDER_KEYS = "GSI2PK = :pk"
STATUS_NAME = {"#status": "status"}
TTL_NAME = {"#ttl": "ttl"}
NAME_NAME = {"#name": "name"}


@dataclass(frozen=True, slots=True)
class DeliveryWrite:
    condition: str
    expression: str
    values: dict[str, AttributeValueTypeDef]


@dataclass(frozen=True, slots=True)
class HistoryWindow:
    field: SearchField
    kind: Product | None
    months: tuple[str, ...]
    number: E164 | None
    since: str
    until: str


class MessagingRepo(Protocol):
    async def claim(self, row: MessageRow) -> bool: ...

    async def claim_attempt(self, key: MessageKey, at: datetime) -> bool: ...

    async def record_inbound(
        self, row: MessageRow, inbound_message_id: str, now: datetime
    ) -> bool: ...

    async def find_claim(
        self, account_id: str, campaign_id: str, destination: E164
    ) -> MessageKey | None: ...

    async def find_by_provider_id(self, provider_message_id: str) -> MessageRow | None: ...

    async def get(self, key: MessageKey) -> MessageRow | None: ...

    async def mark_sent(
        self, key: MessageKey, provider_message_id: str, sent_at: datetime
    ) -> bool: ...

    async def refuse(self, key: MessageKey, reason: str) -> bool: ...

    async def apply_delivery(
        self, key: MessageKey, update: DeliveryUpdate
    ) -> MessageRow | None: ...

    async def count_send(self, account_id: str, day: date) -> int: ...

    async def sends_on(self, account_id: str, day: date) -> int: ...

    async def history_page(
        self, account_id: str, month: str, window: HistoryWindow, start: str | None, limit: int
    ) -> tuple[list[MessageRow], str | None]: ...

    async def conversation_page(
        self, account_id: str, peer: E164, cursor: str | None, limit: int
    ) -> tuple[list[MessageRow], str | None]: ...

    async def put_template(self, account_id: str, template: Template) -> bool: ...

    async def list_templates(self, account_id: str) -> list[Template]: ...

    async def edit_template(
        self, account_id: str, template_id: str, name: str, body: str
    ) -> Template | None: ...

    async def delete_template(self, account_id: str, template_id: str) -> bool: ...


def attribute_of(value: object) -> AttributeValueTypeDef:
    match value:
        case bool():
            return {"BOOL": value}
        case int():
            return n(value)
        case datetime():
            return s(sort_ts(value))
        case str():
            return s(str(value))
        case list():
            return {"L": [attribute_of(item) for item in value]}
        case dict():
            return {"M": {str(name): attribute_of(item) for name, item in value.items()}}
        case _:
            raise Internal(f"unsupported attribute {type(value).__name__}")


def value_of(attribute: AttributeValueTypeDef) -> object:
    if "S" in attribute:
        return attribute["S"]
    if "N" in attribute:
        return int(attribute["N"])
    if "BOOL" in attribute:
        return attribute["BOOL"]
    if "L" in attribute:
        return [value_of(item) for item in attribute["L"]]
    if "M" in attribute:
        return {name: value_of(item) for name, item in attribute["M"].items()}
    return None


def item_of(model: Model) -> dict[str, AttributeValueTypeDef]:
    return {
        name: attribute_of(value) for name, value in model.model_dump(exclude_none=True).items()
    }


def row_of(item: dict[str, AttributeValueTypeDef]) -> MessageRow:
    return MessageRow.model_validate({name: value_of(value) for name, value in item.items()})


def template_of(item: dict[str, AttributeValueTypeDef]) -> Template:
    return Template.model_validate({name: value_of(value) for name, value in item.items()})


def epoch_seconds(moment: datetime) -> int:
    return int(moment.timestamp())


def start_of(day: date) -> datetime:
    return datetime.combine(day, time.min, UTC)


def key_of(message_key: MessageKey) -> dict[str, AttributeValueTypeDef]:
    return key(message_key.pk, message_key.sk)


def marker_key_of(
    account_id: str, campaign_id: str, destination: E164
) -> dict[str, AttributeValueTypeDef]:
    return key(partition("ACCOUNT", account_id), f"SENT#{campaign_id}#{destination}")


def cap_key_of(account_id: str, day: date) -> dict[str, AttributeValueTypeDef]:
    return key(partition("CAP", f"{account_id}#{day.isoformat()}"), METADATA_SK)


def template_key_of(account_id: str, template_id: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition("ACCOUNT", account_id), f"{TEMPLATE_PREFIX}{template_id}")


def inbound_marker_key_of(
    account_id: str, inbound_message_id: str
) -> dict[str, AttributeValueTypeDef]:
    return key(partition("ACCOUNT", account_id), f"{INBOUND_MARKER_PREFIX}{inbound_message_id}")


def conversation_partition(account_id: str, peer: str) -> str:
    return partition("CONV", f"{account_id}#{peer}")


def conversation_start_key(
    account_id: str, peer: E164, message_id: str
) -> dict[str, AttributeValueTypeDef]:
    minted = minted_at(message_id)
    return key_of(message_key_for(account_id, message_id)) | {
        "GSI1PK": s(conversation_partition(account_id, peer)),
        "GSI1SK": s(sort_ts(minted)),
    }


def attribute_of_field(field: SearchField) -> str:
    match field:
        case SearchField.FROM:
            return "from"
        case SearchField.TO:
            return "to"
        case _:
            assert_never(field)


def delivery_values(update: DeliveryUpdate) -> dict[str, AttributeValueTypeDef]:
    return {
        ":at": s(sort_ts(update.at)),
        ":gsi2pk": s(partition("PMSG", update.provider_message_id)),
        ":providerMessageId": s(update.provider_message_id),
        ":queued": s(MessageStatus.QUEUED),
        ":status": s(update.status),
    }


def delivery_write(update: DeliveryUpdate) -> DeliveryWrite:
    values = delivery_values(update)
    sent = {":sent": s(MessageStatus.SENT)}

    match update.status:
        case MessageStatus.SENT:
            return DeliveryWrite(condition=IF_QUEUED, expression=RECORD_SENT, values=values)
        case MessageStatus.DELIVERED:
            return DeliveryWrite(
                condition=IF_NOT_FINAL, expression=RECORD_DELIVERED, values=values | sent
            )
        case MessageStatus.FAILED:
            return DeliveryWrite(
                condition=IF_NOT_FINAL,
                expression=RECORD_FAILED,
                values=values | sent | {":failureReason": s(update.event_type)},
            )
        case _:
            assert_never(update.status)


def history_request(
    table: str,
    pk: str,
    window: HistoryWindow,
    start: dict[str, AttributeValueTypeDef] | None,
    limit: int,
) -> QueryInputTypeDef:
    values = {":pk": s(pk), ":since": s(window.since), ":until": s(window.until)}
    filters: list[str] = []
    request: QueryInputTypeDef = {
        "KeyConditionExpression": HISTORY_KEYS,
        "Limit": limit,
        "ScanIndexForward": False,
        "TableName": table,
    }

    if window.number is not None:
        filters.append(NUMBER_FILTER)
        values[":number"] = s(window.number)
        request["ExpressionAttributeNames"] = {"#field": attribute_of_field(window.field)}
    if window.kind is not None:
        filters.append(KIND_FILTER)
        values[":kind"] = s(window.kind)
    if filters:
        request["FilterExpression"] = " AND ".join(filters)
    if start is not None:
        request["ExclusiveStartKey"] = start

    request["ExpressionAttributeValues"] = values
    return request


@dataclass(frozen=True, slots=True)
class MessagingDynamoRepo:
    table: Table

    async def claim(self, row: MessageRow) -> bool:
        message_key = row.key
        thread = partition("CONV", f"{row.account_id}#{row.to}")
        message_item = (
            item_of(row)
            | key_of(message_key)
            | {
                "GSI1PK": s(thread),
                "GSI1SK": s(sort_ts(row.queued_at)),
                "ttl": n(epoch_seconds(row.queued_at + MESSAGE_TTL)),
            }
        )
        marker_item = marker_key_of(row.account_id, row.campaign_id, row.to) | {
            "messageId": s(row.message_id),
            "messageKey": s(str(message_key)),
            "ttl": n(epoch_seconds(row.queued_at + MARKER_TTL)),
        }

        write = condition_failed_as_false(self.table.client.transact_write_items)
        return await write(
            TransactItems=[
                {
                    "Put": {
                        "ConditionExpression": IF_ABSENT,
                        "Item": message_item,
                        "TableName": self.table.name,
                    }
                },
                {
                    "Put": {
                        "ConditionExpression": IF_ABSENT,
                        "Item": marker_item,
                        "TableName": self.table.name,
                    }
                },
            ]
        )

    async def record_inbound(self, row: MessageRow, inbound_message_id: str, now: datetime) -> bool:
        thread = conversation_partition(row.account_id, row.from_)
        message_item = (
            item_of(row)
            | key_of(row.key)
            | {
                "GSI1PK": s(thread),
                "GSI1SK": s(sort_ts(row.queued_at)),
                "ttl": n(epoch_seconds(now + MESSAGE_TTL)),
            }
        )
        marker_item = inbound_marker_key_of(row.account_id, inbound_message_id) | {
            "ttl": n(epoch_seconds(now + MARKER_TTL)),
        }

        write = condition_failed_as_false(self.table.client.transact_write_items)
        return await write(
            TransactItems=[
                {
                    "Put": {
                        "ConditionExpression": IF_ABSENT,
                        "Item": message_item,
                        "TableName": self.table.name,
                    }
                },
                {
                    "Put": {
                        "ConditionExpression": IF_ABSENT,
                        "Item": marker_item,
                        "TableName": self.table.name,
                    }
                },
            ]
        )

    async def claim_attempt(self, key: MessageKey, at: datetime) -> bool:
        updated = await self._update(
            {
                "ConditionExpression": IF_UNATTEMPTED,
                "ExpressionAttributeNames": STATUS_NAME,
                "ExpressionAttributeValues": {
                    ":at": s(sort_ts(at)),
                    ":queued": s(MessageStatus.QUEUED),
                },
                "Key": key_of(key),
                "TableName": self.table.name,
                "UpdateExpression": CLAIM_ATTEMPT,
            }
        )
        return updated is not None

    async def find_claim(
        self, account_id: str, campaign_id: str, destination: E164
    ) -> MessageKey | None:
        output = await self.table.client.get_item(
            Key=marker_key_of(account_id, campaign_id, destination), TableName=self.table.name
        )
        item = output.get("Item")
        if item is None:
            return None
        return MessageKey.parse(item["messageKey"]["S"])

    async def find_by_provider_id(self, provider_message_id: str) -> MessageRow | None:
        output = await self.table.client.query(
            ExpressionAttributeValues={":pk": s(partition("PMSG", provider_message_id))},
            IndexName=GSI2,
            KeyConditionExpression=PROVIDER_KEYS,
            Limit=1,
            TableName=self.table.name,
        )
        items = output["Items"]
        return row_of(items[0]) if items else None

    async def get(self, key: MessageKey) -> MessageRow | None:
        output = await self.table.client.get_item(Key=key_of(key), TableName=self.table.name)
        item = output.get("Item")
        return row_of(item) if item is not None else None

    async def mark_sent(self, key: MessageKey, provider_message_id: str, sent_at: datetime) -> bool:
        updated = await self._update(
            {
                "ConditionExpression": IF_QUEUED,
                "ExpressionAttributeNames": STATUS_NAME,
                "ExpressionAttributeValues": {
                    ":at": s(sort_ts(sent_at)),
                    ":gsi2pk": s(partition("PMSG", provider_message_id)),
                    ":providerMessageId": s(provider_message_id),
                    ":queued": s(MessageStatus.QUEUED),
                    ":status": s(MessageStatus.SENT),
                },
                "Key": key_of(key),
                "TableName": self.table.name,
                "UpdateExpression": MARK_SENT,
            }
        )
        return updated is not None

    async def refuse(self, key: MessageKey, reason: str) -> bool:
        updated = await self._update(
            {
                "ConditionExpression": IF_QUEUED,
                "ExpressionAttributeNames": STATUS_NAME,
                "ExpressionAttributeValues": {
                    ":failureReason": s(reason),
                    ":queued": s(MessageStatus.QUEUED),
                    ":status": s(MessageStatus.FAILED),
                },
                "Key": key_of(key),
                "TableName": self.table.name,
                "UpdateExpression": REFUSE,
            }
        )
        return updated is not None

    async def apply_delivery(self, key: MessageKey, update: DeliveryUpdate) -> MessageRow | None:
        write = delivery_write(update)
        updated = await self._update(
            {
                "ConditionExpression": write.condition,
                "ExpressionAttributeNames": STATUS_NAME,
                "ExpressionAttributeValues": write.values,
                "Key": key_of(key),
                "ReturnValues": "ALL_NEW",
                "TableName": self.table.name,
                "UpdateExpression": write.expression,
            }
        )
        return row_of(updated) if updated is not None else None

    async def count_send(self, account_id: str, day: date) -> int:
        counted = await self._update(
            {
                "ExpressionAttributeNames": TTL_NAME,
                "ExpressionAttributeValues": {
                    ":one": n(1),
                    ":ttl": n(epoch_seconds(start_of(day) + CAP_TTL)),
                },
                "Key": cap_key_of(account_id, day),
                "ReturnValues": "UPDATED_NEW",
                "TableName": self.table.name,
                "UpdateExpression": COUNT_SEND,
            }
        )
        if counted is None:
            raise Internal(COUNTER_LOST)
        return int(counted["n"]["N"])

    async def sends_on(self, account_id: str, day: date) -> int:
        output = await self.table.client.get_item(
            Key=cap_key_of(account_id, day), TableName=self.table.name
        )
        item = output.get("Item")
        return int(item["n"]["N"]) if item is not None else 0

    async def history_page(
        self, account_id: str, month: str, window: HistoryWindow, start: str | None, limit: int
    ) -> tuple[list[MessageRow], str | None]:
        pk = message_partition(account_id, month)
        rows: list[MessageRow] = []
        exclusive_start = key(pk, start) if start is not None else None

        for _ in range(MAX_QUERY_PAGES):
            request = history_request(
                self.table.name, pk, window, exclusive_start, limit - len(rows)
            )
            output = await self.table.client.query(**request)
            rows.extend(row_of(item) for item in output["Items"])

            exclusive_start = output.get("LastEvaluatedKey")
            if exclusive_start is None or len(rows) >= limit:
                break

        return rows, exclusive_start["SK"]["S"] if exclusive_start is not None else None

    async def conversation_page(
        self, account_id: str, peer: E164, cursor: str | None, limit: int
    ) -> tuple[list[MessageRow], str | None]:
        request: QueryInputTypeDef = {
            "ExpressionAttributeValues": {":pk": s(conversation_partition(account_id, peer))},
            "IndexName": GSI1,
            "KeyConditionExpression": CONVERSATION_KEYS,
            "Limit": limit,
            "ScanIndexForward": False,
            "TableName": self.table.name,
        }
        if cursor is not None:
            request["ExclusiveStartKey"] = conversation_start_key(account_id, peer, cursor)

        output = await self.table.client.query(**request)
        rows = [row_of(item) for item in output["Items"]]
        more = output.get("LastEvaluatedKey") is not None
        return rows, rows[-1].message_id if more and rows else None

    async def put_template(self, account_id: str, template: Template) -> bool:
        write = condition_failed_as_false(self.table.client.put_item)
        return await write(
            ConditionExpression=IF_ABSENT,
            Item=item_of(template) | template_key_of(account_id, template.template_id),
            TableName=self.table.name,
        )

    async def list_templates(self, account_id: str) -> list[Template]:
        templates: list[Template] = []
        request: QueryInputTypeDef = {
            "ExpressionAttributeValues": {
                ":pk": s(partition("ACCOUNT", account_id)),
                ":prefix": s(TEMPLATE_PREFIX),
            },
            "KeyConditionExpression": TEMPLATE_KEYS,
            "TableName": self.table.name,
        }

        items = await paged_items(self.table.client, request, MAX_QUERY_PAGES, TEMPLATES_UNBOUNDED)
        templates.extend(template_of(item) for item in items)
        return templates

    async def edit_template(
        self, account_id: str, template_id: str, name: str, body: str
    ) -> Template | None:
        updated = await self._update(
            {
                "ConditionExpression": IF_PRESENT,
                "ExpressionAttributeNames": NAME_NAME,
                "ExpressionAttributeValues": {":body": s(body), ":name": s(name)},
                "Key": template_key_of(account_id, template_id),
                "ReturnValues": "ALL_NEW",
                "TableName": self.table.name,
                "UpdateExpression": EDIT_TEMPLATE,
            }
        )
        return template_of(updated) if updated is not None else None

    async def delete_template(self, account_id: str, template_id: str) -> bool:
        write = condition_failed_as_false(self.table.client.delete_item)
        return await write(
            ConditionExpression=IF_PRESENT,
            Key=template_key_of(account_id, template_id),
            TableName=self.table.name,
        )

    async def _update(
        self, request: UpdateItemInputTypeDef
    ) -> dict[str, AttributeValueTypeDef] | None:
        attributes: dict[str, AttributeValueTypeDef] = {}

        async def write() -> None:
            output = await self.table.client.update_item(**request)
            attributes.update(output.get("Attributes", {}))

        if not await condition_failed_as_false(write)():
            return None
        return attributes

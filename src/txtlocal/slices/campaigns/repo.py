from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from txtlocal.shared.table import (
    IF_PRESENT,
    Table,
    condition_failed_as_false,
    key,
    n,
    partition,
    s,
    sort_ts,
)
from txtlocal.slices.campaigns.model import (
    Campaign,
    CampaignCounter,
    CampaignCounts,
    CampaignPage,
    CampaignQuery,
    CampaignRef,
    CampaignStatus,
    FanoutStep,
    SchedulePlan,
)

if TYPE_CHECKING:
    from types_aiobotocore_dynamodb.type_defs import AttributeValueTypeDef, QueryInputTypeDef

    from txtlocal.shared.money import Micro

ACCOUNT = "ACCOUNT"
CAMPAIGN_PREFIX = "CAMPAIGN#"
DUE = "DUE"
DUE_INDEX = "GSI1"
DUE_TICK = timedelta(milliseconds=1)
PAGE_SIZE = 20
RETENTION = timedelta(days=400)
SENDING = "SENDING"

ACCOUNT_PREFIX = partition(ACCOUNT, "")
DUE_PARTITION = partition(DUE, "")
SENDING_PARTITION = partition(SENDING, "")

BY_ACCOUNT = "PK = :pk AND begins_with(SK, :prefix)"
BY_CHANNEL = "channel = :channel"
BY_NAME = "contains(#name, :q)"
CLAIM_DRAFT = "#status = :draft"
CLAIM_DUE = "#status = :scheduled OR (#status = :sending AND claimedAt < :stale)"
CLEAR_INDEX = "REMOVE GSI1PK, GSI1SK"
COMPLETE_WHEN_COUNTED = (
    "#status = :sending AND #counts.#sent = :sent_count AND #counts.#refused = :refused_count"
)
COUNT_ONE = (
    "SET #counts.#counter = if_not_exists(#counts.#counter, :zero) + :one, "
    "GSI1SK = :progress, lastProgressAt = :now"
)
IF_ABSENT = "attribute_not_exists(PK)"
INDEX_BEFORE = "GSI1PK = :partition AND GSI1SK < :ceiling"
IS_DRAFT = "attribute_exists(PK) AND #status = :draft"
IS_SCHEDULED = "#status = :scheduled"
IS_UNSETTLED = "#status = :sent AND attribute_not_exists(settledMicro)"
MARK_SETTLED = "SET settledMicro = :settled_micro REMOVE GSI1PK, GSI1SK"

COUNTED_BATCH = (
    "#counts.#queued = if_not_exists(#counts.#queued, :zero) + :queued, "
    "#counts.#refused = if_not_exists(#counts.#refused, :zero) + :refused, "
    "#counts.#recipients = :recipients"
)
FANOUT_DONE = (
    f"SET {COUNTED_BATCH}, GSI1PK = :sending, GSI1SK = :progress, lastProgressAt = :now "
    "REMOVE fanoutCursor"
)
FANOUT_STEP = f"SET {COUNTED_BATCH}, fanoutCursor = :cursor, lastProgressAt = :now"
SET_CANCELLED = (
    "SET #status = :cancelled, completedAt = :completed_at, settledMicro = :zero, #ttl = :ttl "
    "REMOVE GSI1PK, GSI1SK"
)
SET_SCHEDULED = (
    "SET #status = :scheduled, scheduledAt = :scheduled_at, GSI1PK = :due, GSI1SK = :due_sk, "
    "#counts.#recipients = :recipients, quoteMicro = :quote_micro, reservedMicro = :reserved_micro"
)
SET_CLAIMED = "SET #status = :sending, claimedAt = :claimed_at"
SET_SENDING = (
    "SET #status = :sending, GSI1PK = :sending_index, GSI1SK = :progress, lastProgressAt = :now"
)
SET_SENT = (
    "SET #status = :sent, completedAt = :completed_at, "
    "GSI1PK = :sending_index, GSI1SK = :progress, #ttl = :ttl"
)

COMPLETE_NAMES = {
    "#counts": "counts",
    "#refused": "refused",
    "#sent": "sent",
    "#status": "status",
    "#ttl": "ttl",
}
COUNTS_NAMES = {
    "#counts": "counts",
    "#queued": "queued",
    "#recipients": "recipients",
    "#refused": "refused",
}
SCHEDULE_NAMES = {"#counts": "counts", "#recipients": "recipients", "#status": "status"}
STATUS_NAME = {"#status": "status"}


def sort_key(campaign_id: str) -> str:
    return f"{CAMPAIGN_PREFIX}{campaign_id}"


def campaign_key(account_id: str, campaign_id: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(ACCOUNT, account_id), sort_key(campaign_id))


def index_sort_key(moment: datetime, account_id: str, campaign_id: str) -> str:
    return f"{sort_ts(moment)}#{account_id}#{campaign_id}"


def expires_at(now: datetime) -> int:
    return int((now + RETENTION).timestamp())


def to_attr(value: object) -> AttributeValueTypeDef:
    match value:
        case bool():
            return {"BOOL": value}
        case int():
            return {"N": str(value)}
        case str():
            return {"S": value}
        case list():
            return {"L": [to_attr(item) for item in value]}
        case dict():
            return {"M": {name: to_attr(item) for name, item in value.items()}}
        case _:
            raise TypeError(type(value).__name__)


def from_attr(attr: AttributeValueTypeDef) -> object:
    match attr:
        case {"S": text}:
            return text
        case {"N": number}:
            return int(number)
        case {"BOOL": flag}:
            return flag
        case {"L": items}:
            return [from_attr(item) for item in items]
        case {"M": members}:
            return {name: from_attr(member) for name, member in members.items()}
        case _:
            raise TypeError(str(attr))


def item_of(account_id: str, campaign: Campaign) -> dict[str, AttributeValueTypeDef]:
    fields = campaign.model_dump(by_alias=True, exclude_none=True, mode="json")
    attributes = {name: to_attr(value) for name, value in fields.items()}
    return {**campaign_key(account_id, campaign.campaign_id), **attributes}


def campaign_of(item: Mapping[str, AttributeValueTypeDef]) -> Campaign:
    return Campaign.model_validate(from_attr({"M": item}))


def ref_of(item: Mapping[str, AttributeValueTypeDef]) -> CampaignRef:
    return CampaignRef(
        account_id=item["PK"]["S"].removeprefix(ACCOUNT_PREFIX),
        campaign_id=item["SK"]["S"].removeprefix(CAMPAIGN_PREFIX),
    )


def page_params(table_name: str, pk: str, query: CampaignQuery) -> QueryInputTypeDef:
    names: dict[str, str] = {}
    values: dict[str, AttributeValueTypeDef] = {":pk": s(pk), ":prefix": s(CAMPAIGN_PREFIX)}
    filters: list[str] = []

    if query.kind is not None:
        values[":channel"] = s(query.kind)
        filters.append(BY_CHANNEL)
    if query.q:
        names["#name"] = "name"
        values[":q"] = s(query.q)
        filters.append(BY_NAME)

    params: QueryInputTypeDef = {
        "ExpressionAttributeValues": values,
        "KeyConditionExpression": BY_ACCOUNT,
        "Limit": PAGE_SIZE,
        "ScanIndexForward": False,
        "TableName": table_name,
    }
    if names:
        params["ExpressionAttributeNames"] = names
    if filters:
        params["FilterExpression"] = " AND ".join(filters)
    if query.cursor is not None:
        params["ExclusiveStartKey"] = key(pk, sort_key(query.cursor))

    return params


class CampaignsRepo(Protocol):
    async def add_count(
        self, account_id: str, campaign_id: str, counter: CampaignCounter, now: datetime
    ) -> Campaign: ...

    async def advance_fanout(
        self, account_id: str, campaign_id: str, step: FanoutStep
    ) -> Campaign: ...

    async def cancel_scheduled(self, account_id: str, campaign_id: str, now: datetime) -> bool: ...

    async def claim_draft(self, account_id: str, campaign_id: str, now: datetime) -> bool: ...

    async def claim_due(
        self, account_id: str, campaign_id: str, now: datetime, stale_before: datetime
    ) -> bool: ...

    async def clear_index(self, account_id: str, campaign_id: str) -> bool: ...

    async def complete(
        self, account_id: str, campaign_id: str, counts: CampaignCounts, now: datetime
    ) -> bool: ...

    async def delete_draft(self, account_id: str, campaign_id: str) -> bool: ...

    async def mark_settled(
        self, account_id: str, campaign_id: str, settled_micro: Micro
    ) -> bool: ...

    async def due(self, now: datetime, limit: int) -> list[CampaignRef]: ...

    async def get(self, account_id: str, campaign_id: str) -> Campaign | None: ...

    async def page(self, account_id: str, query: CampaignQuery) -> CampaignPage: ...

    async def put_draft(self, account_id: str, campaign: Campaign) -> bool: ...

    async def save_draft(self, account_id: str, campaign: Campaign) -> bool: ...

    async def schedule(self, account_id: str, campaign_id: str, plan: SchedulePlan) -> bool: ...

    async def stuck(self, before: datetime, limit: int) -> list[CampaignRef]: ...


@dataclass(frozen=True, slots=True)
class CampaignsDynamoRepo:
    table: Table

    async def add_count(
        self, account_id: str, campaign_id: str, counter: CampaignCounter, now: datetime
    ) -> Campaign:
        response = await self.table.client.update_item(
            ExpressionAttributeNames={"#counter": counter, "#counts": "counts"},
            ExpressionAttributeValues={
                ":now": s(sort_ts(now)),
                ":one": n(1),
                ":progress": s(index_sort_key(now, account_id, campaign_id)),
                ":zero": n(0),
            },
            Key=campaign_key(account_id, campaign_id),
            ReturnValues="ALL_NEW",
            TableName=self.table.name,
            UpdateExpression=COUNT_ONE,
        )
        return campaign_of(response["Attributes"])

    async def advance_fanout(self, account_id: str, campaign_id: str, step: FanoutStep) -> Campaign:
        done = step.cursor is None
        moving = (
            {
                ":progress": s(index_sort_key(step.at, account_id, campaign_id)),
                ":sending": s(SENDING_PARTITION),
            }
            if done
            else {":cursor": s(step.cursor or "")}
        )
        response = await self.table.client.update_item(
            ExpressionAttributeNames=COUNTS_NAMES,
            ExpressionAttributeValues={
                ":now": s(sort_ts(step.at)),
                ":queued": n(step.queued),
                ":recipients": n(step.recipients),
                ":refused": n(step.refused),
                ":zero": n(0),
                **moving,
            },
            Key=campaign_key(account_id, campaign_id),
            ReturnValues="ALL_NEW",
            TableName=self.table.name,
            UpdateExpression=FANOUT_DONE if done else FANOUT_STEP,
        )
        return campaign_of(response["Attributes"])

    async def cancel_scheduled(self, account_id: str, campaign_id: str, now: datetime) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IS_SCHEDULED,
            ExpressionAttributeNames={**STATUS_NAME, "#ttl": "ttl"},
            ExpressionAttributeValues={
                ":cancelled": s(CampaignStatus.CANCELLED),
                ":completed_at": s(sort_ts(now)),
                ":scheduled": s(CampaignStatus.SCHEDULED),
                ":ttl": n(expires_at(now)),
                ":zero": n(0),
            },
            Key=campaign_key(account_id, campaign_id),
            TableName=self.table.name,
            UpdateExpression=SET_CANCELLED,
        )

    async def claim_draft(self, account_id: str, campaign_id: str, now: datetime) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=CLAIM_DRAFT,
            ExpressionAttributeNames=STATUS_NAME,
            ExpressionAttributeValues={
                ":draft": s(CampaignStatus.DRAFT),
                ":now": s(sort_ts(now)),
                ":progress": s(index_sort_key(now, account_id, campaign_id)),
                ":sending": s(CampaignStatus.SENDING),
                ":sending_index": s(SENDING_PARTITION),
            },
            Key=campaign_key(account_id, campaign_id),
            TableName=self.table.name,
            UpdateExpression=SET_SENDING,
        )

    async def claim_due(
        self, account_id: str, campaign_id: str, now: datetime, stale_before: datetime
    ) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=CLAIM_DUE,
            ExpressionAttributeNames=STATUS_NAME,
            ExpressionAttributeValues={
                ":claimed_at": s(sort_ts(now)),
                ":scheduled": s(CampaignStatus.SCHEDULED),
                ":sending": s(CampaignStatus.SENDING),
                ":stale": s(sort_ts(stale_before)),
            },
            Key=campaign_key(account_id, campaign_id),
            TableName=self.table.name,
            UpdateExpression=SET_CLAIMED,
        )

    async def clear_index(self, account_id: str, campaign_id: str) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            Key=campaign_key(account_id, campaign_id),
            TableName=self.table.name,
            UpdateExpression=CLEAR_INDEX,
        )

    async def complete(
        self, account_id: str, campaign_id: str, counts: CampaignCounts, now: datetime
    ) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=COMPLETE_WHEN_COUNTED,
            ExpressionAttributeNames=COMPLETE_NAMES,
            ExpressionAttributeValues={
                ":completed_at": s(sort_ts(now)),
                ":progress": s(index_sort_key(now, account_id, campaign_id)),
                ":refused_count": n(counts.refused),
                ":sending": s(CampaignStatus.SENDING),
                ":sending_index": s(SENDING_PARTITION),
                ":sent": s(CampaignStatus.SENT),
                ":sent_count": n(counts.sent),
                ":ttl": n(expires_at(now)),
            },
            Key=campaign_key(account_id, campaign_id),
            TableName=self.table.name,
            UpdateExpression=SET_SENT,
        )

    async def mark_settled(self, account_id: str, campaign_id: str, settled_micro: Micro) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IS_UNSETTLED,
            ExpressionAttributeNames=STATUS_NAME,
            ExpressionAttributeValues={
                ":sent": s(CampaignStatus.SENT),
                ":settled_micro": n(settled_micro),
            },
            Key=campaign_key(account_id, campaign_id),
            TableName=self.table.name,
            UpdateExpression=MARK_SETTLED,
        )

    async def delete_draft(self, account_id: str, campaign_id: str) -> bool:
        return await condition_failed_as_false(self.table.client.delete_item)(
            ConditionExpression=IS_DRAFT,
            ExpressionAttributeNames=STATUS_NAME,
            ExpressionAttributeValues={":draft": s(CampaignStatus.DRAFT)},
            Key=campaign_key(account_id, campaign_id),
            TableName=self.table.name,
        )

    async def due(self, now: datetime, limit: int) -> list[CampaignRef]:
        return await self._before(DUE_PARTITION, now + DUE_TICK, limit)

    async def stuck(self, before: datetime, limit: int) -> list[CampaignRef]:
        return await self._before(SENDING_PARTITION, before, limit)

    async def _before(
        self, index_partition: str, ceiling: datetime, limit: int
    ) -> list[CampaignRef]:
        response = await self.table.client.query(
            ExpressionAttributeValues={
                ":ceiling": s(sort_ts(ceiling)),
                ":partition": s(index_partition),
            },
            IndexName=DUE_INDEX,
            KeyConditionExpression=INDEX_BEFORE,
            Limit=limit,
            TableName=self.table.name,
        )
        return [ref_of(item) for item in response["Items"]]

    async def get(self, account_id: str, campaign_id: str) -> Campaign | None:
        response = await self.table.client.get_item(
            Key=campaign_key(account_id, campaign_id), TableName=self.table.name
        )
        item = response.get("Item")
        return None if item is None else campaign_of(item)

    async def page(self, account_id: str, query: CampaignQuery) -> CampaignPage:
        pk = partition(ACCOUNT, account_id)
        response = await self.table.client.query(**page_params(self.table.name, pk, query))

        last = response.get("LastEvaluatedKey")
        return CampaignPage(
            cursor=None if last is None else last["SK"]["S"].removeprefix(CAMPAIGN_PREFIX),
            items=[campaign_of(item) for item in response["Items"]],
        )

    async def put_draft(self, account_id: str, campaign: Campaign) -> bool:
        return await condition_failed_as_false(self.table.client.put_item)(
            ConditionExpression=IF_ABSENT,
            Item=item_of(account_id, campaign),
            TableName=self.table.name,
        )

    async def save_draft(self, account_id: str, campaign: Campaign) -> bool:
        return await condition_failed_as_false(self.table.client.put_item)(
            ConditionExpression=IS_DRAFT,
            ExpressionAttributeNames=STATUS_NAME,
            ExpressionAttributeValues={":draft": s(CampaignStatus.DRAFT)},
            Item=item_of(account_id, campaign),
            TableName=self.table.name,
        )

    async def schedule(self, account_id: str, campaign_id: str, plan: SchedulePlan) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=CLAIM_DRAFT,
            ExpressionAttributeNames=SCHEDULE_NAMES,
            ExpressionAttributeValues={
                ":draft": s(CampaignStatus.DRAFT),
                ":due": s(DUE_PARTITION),
                ":due_sk": s(index_sort_key(plan.scheduled_at, account_id, campaign_id)),
                ":quote_micro": n(plan.quote_micro),
                ":recipients": n(plan.recipients),
                ":reserved_micro": n(plan.reserved_micro),
                ":scheduled": s(CampaignStatus.SCHEDULED),
                ":scheduled_at": s(sort_ts(plan.scheduled_at)),
            },
            Key=campaign_key(account_id, campaign_id),
            TableName=self.table.name,
            UpdateExpression=SET_SCHEDULED,
        )

import asyncio
import itertools
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from txtlocal.shared.errors import Internal, Upstream
from txtlocal.shared.table import (
    APP,
    IF_PRESENT,
    METADATA_SK,
    Table,
    backoff,
    condition_failed_as_false,
    key,
    n,
    partition,
    s,
)
from txtlocal.slices.developer.model import IdempotencyStatus, LogFilters, LogRow

if TYPE_CHECKING:
    from types_aiobotocore_dynamodb.type_defs import AttributeValueTypeDef, WriteRequestTypeDef
    from types_aiobotocore_logs import CloudWatchLogsClient
    from types_aiobotocore_logs.type_defs import ResultFieldTypeDef

API_CAMPAIGN = "DEVAPICAMPAIGN"
BATCH_GET_SIZE = 100
BATCH_WRITE_SIZE = 25
CUSTOM_STRING = "DEVCUSTOM"
CUSTOM_STRING_PREFIX = f"{APP}#{CUSTOM_STRING}#"
IDEMPOTENCY = "IDEM"
IDEMPOTENCY_TTL = timedelta(hours=24)

IF_ABSENT = "attribute_not_exists(PK)"

INSIGHTS_TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S.%f"
QUERY_FIELDS = "fields @timestamp, request_id, user_id, route, method, status, latency_ms, outcome"
QUERY_PENDING_STATUSES = frozenset({"Scheduled", "Running"})
BATCH_RETRY_ATTEMPTS = 8
QUERY_ROW_LIMIT = 400
UNPROCESSED_READS = "a batch read of custom strings did not finish"
UNPROCESSED_WRITES = "a batch write of custom strings did not finish"
QUERY_TERMINAL_FAILURES = frozenset({"Cancelled", "Failed", "Timeout", "Unknown"})

FINISH_IDEMPOTENCY = (
    "SET #status = :status, #responseStatus = :responseStatus, #responseBody = :responseBody"
)
FINISH_IDEMPOTENCY_NAMES = {
    "#responseBody": "responseBody",
    "#responseStatus": "responseStatus",
    "#status": "status",
}


@dataclass(frozen=True, slots=True)
class IdempotencyRecord:
    response_body: str | None
    response_status: int | None
    status: IdempotencyStatus


class DeveloperRepo(Protocol):
    async def api_campaign_id(self, account_id: str) -> str | None: ...

    async def begin_idempotency(
        self, user_id: str, idempotency_key: str, now: datetime
    ) -> bool: ...

    async def custom_strings_of(self, message_ids: Sequence[str]) -> dict[str, str]: ...

    async def finish_idempotency(
        self, user_id: str, idempotency_key: str, status: int, body: str
    ) -> None: ...

    async def peek_idempotency(
        self, user_id: str, idempotency_key: str
    ) -> IdempotencyRecord | None: ...

    async def remember_api_campaign_id(self, account_id: str, campaign_id: str) -> bool: ...

    async def remember_custom_strings(self, entries: Mapping[str, str]) -> None: ...


def epoch_seconds(moment: datetime) -> int:
    return int(moment.timestamp())


def idempotency_row_key(user_id: str, idempotency_key: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(IDEMPOTENCY, f"{user_id}#{idempotency_key}"), METADATA_SK)


def api_campaign_row_key(account_id: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(API_CAMPAIGN, account_id), METADATA_SK)


def custom_string_row_key(message_id: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(CUSTOM_STRING, message_id), METADATA_SK)


def text_of(item: Mapping[str, AttributeValueTypeDef], field: str) -> str:
    match item.get(field):
        case {"S": str(value)}:
            return value
        case _:
            raise Internal(f"{field} missing or malformed")


def optional_text_of(item: Mapping[str, AttributeValueTypeDef], field: str) -> str | None:
    match item.get(field):
        case {"S": str(value)}:
            return value
        case _:
            return None


def optional_int_of(item: Mapping[str, AttributeValueTypeDef], field: str) -> int | None:
    match item.get(field):
        case {"N": str(value)}:
            return int(value)
        case _:
            return None


def idempotency_record_of(item: Mapping[str, AttributeValueTypeDef]) -> IdempotencyRecord:
    return IdempotencyRecord(
        response_body=optional_text_of(item, "responseBody"),
        response_status=optional_int_of(item, "responseStatus"),
        status=IdempotencyStatus(text_of(item, "status")),
    )


@dataclass(frozen=True, slots=True)
class DeveloperDynamoRepo:
    table: Table

    async def api_campaign_id(self, account_id: str) -> str | None:
        item = await self._get(api_campaign_row_key(account_id))
        return None if item is None else text_of(item, "campaignId")

    async def remember_api_campaign_id(self, account_id: str, campaign_id: str) -> bool:
        return await self._put_if(
            {**api_campaign_row_key(account_id), "campaignId": s(campaign_id)}, IF_ABSENT
        )

    async def begin_idempotency(self, user_id: str, idempotency_key: str, now: datetime) -> bool:
        item = {
            **idempotency_row_key(user_id, idempotency_key),
            "status": s(IdempotencyStatus.IN_FLIGHT),
            "ttl": n(epoch_seconds(now + IDEMPOTENCY_TTL)),
        }
        return await self._put_if(item, IF_ABSENT)

    async def peek_idempotency(
        self, user_id: str, idempotency_key: str
    ) -> IdempotencyRecord | None:
        item = await self._get(idempotency_row_key(user_id, idempotency_key))
        return None if item is None else idempotency_record_of(item)

    async def finish_idempotency(
        self, user_id: str, idempotency_key: str, status: int, body: str
    ) -> None:
        await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeNames=FINISH_IDEMPOTENCY_NAMES,
            ExpressionAttributeValues={
                ":responseBody": s(body),
                ":responseStatus": n(status),
                ":status": s(IdempotencyStatus.DONE),
            },
            Key=idempotency_row_key(user_id, idempotency_key),
            TableName=self.table.name,
            UpdateExpression=FINISH_IDEMPOTENCY,
        )

    async def remember_custom_strings(self, entries: Mapping[str, str]) -> None:
        items = list(entries.items())
        for batch in itertools.batched(items, BATCH_WRITE_SIZE, strict=False):
            requests: list[WriteRequestTypeDef] = [
                {
                    "PutRequest": {
                        "Item": {
                            **custom_string_row_key(message_id),
                            "customString": s(custom_string),
                        }
                    }
                }
                for message_id, custom_string in batch
            ]
            pending = requests
            for attempt in range(BATCH_RETRY_ATTEMPTS):
                response = await self.table.client.batch_write_item(
                    RequestItems={self.table.name: pending}
                )
                left = response["UnprocessedItems"].get(self.table.name)
                if not left:
                    break

                pending = cast("list[WriteRequestTypeDef]", left)
                await asyncio.sleep(backoff(attempt))
            else:
                raise Internal(UNPROCESSED_WRITES)

    async def custom_strings_of(self, message_ids: Sequence[str]) -> dict[str, str]:
        found: dict[str, str] = {}
        for batch in itertools.batched(dict.fromkeys(message_ids), BATCH_GET_SIZE, strict=False):
            keys = [custom_string_row_key(message_id) for message_id in batch]
            pending = keys
            for attempt in range(BATCH_RETRY_ATTEMPTS):
                response = await self.table.client.batch_get_item(
                    RequestItems={self.table.name: {"Keys": pending}}
                )
                for item in response["Responses"][self.table.name]:
                    message_id = text_of(item, "PK").removeprefix(CUSTOM_STRING_PREFIX)
                    found[message_id] = text_of(item, "customString")

                unprocessed = response.get("UnprocessedKeys", {}).get(self.table.name)
                if unprocessed is None or not unprocessed["Keys"]:
                    break

                pending = list(unprocessed["Keys"])
                await asyncio.sleep(backoff(attempt))
            else:
                raise Internal(UNPROCESSED_READS)

        return found

    async def _get(
        self, item_key: dict[str, AttributeValueTypeDef]
    ) -> dict[str, AttributeValueTypeDef] | None:
        response = await self.table.client.get_item(
            ConsistentRead=True, Key=item_key, TableName=self.table.name
        )
        return response.get("Item")

    @condition_failed_as_false
    async def _put_if(self, item: dict[str, AttributeValueTypeDef], condition: str) -> None:
        await self.table.client.put_item(
            ConditionExpression=condition, Item=item, TableName=self.table.name
        )


@dataclass(frozen=True, slots=True)
class LogPending:
    query_id: str


@dataclass(frozen=True, slots=True)
class LogRows:
    rows: list[LogRow]


type LogResult = LogPending | LogRows
type LogWindow = tuple[datetime, datetime]


class LogQueries(Protocol):
    async def start(self, account_id: str, filters: LogFilters, window: LogWindow) -> str: ...

    async def poll(self, query_id: str) -> LogResult: ...


def quoted(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def rows_query_string(account_id: str, filters: LogFilters) -> str:
    conditions = [f"account_id = {quoted(account_id)}", 'event = "api_request"']
    if filters.outcome is not None:
        conditions.append(f"outcome = {quoted(filters.outcome)}")
    if filters.route is not None:
        conditions.append(f"route = {quoted(filters.route)}")
    if filters.user_id is not None:
        conditions.append(f"user_id = {quoted(filters.user_id)}")

    return "\n".join(
        [
            QUERY_FIELDS,
            f"| filter {' and '.join(conditions)}",
            "| sort @timestamp desc",
            f"| limit {QUERY_ROW_LIMIT}",
        ]
    )


def insights_timestamp_of(text: str) -> datetime:
    try:
        return datetime.strptime(text, INSIGHTS_TIMESTAMP_FORMAT).replace(tzinfo=UTC)
    except ValueError:
        return datetime.fromtimestamp(0, UTC)


def log_row_of(fields: Sequence[ResultFieldTypeDef]) -> LogRow:
    values = {one["field"]: one["value"] for one in fields if "field" in one and "value" in one}
    return LogRow(
        latency_ms=int(values.get("latency_ms") or 0),
        method=values.get("method", ""),
        outcome=values.get("outcome", ""),
        request_id=values.get("request_id", ""),
        route=values.get("route", ""),
        status=int(values.get("status") or 0),
        timestamp=insights_timestamp_of(values.get("@timestamp", "")),
        user_id=values.get("user_id", ""),
    )


@dataclass(frozen=True, slots=True)
class InsightsLogQueries:
    log_group: str
    logs_client: CloudWatchLogsClient

    async def start(self, account_id: str, filters: LogFilters, window: LogWindow) -> str:
        since, until = window
        response = await self.logs_client.start_query(
            endTime=epoch_seconds(until),
            logGroupName=self.log_group,
            queryString=rows_query_string(account_id, filters),
            startTime=epoch_seconds(since),
        )
        return response["queryId"]

    async def poll(self, query_id: str) -> LogResult:
        response = await self.logs_client.get_query_results(queryId=query_id)
        status = response["status"]
        if status in QUERY_PENDING_STATUSES:
            return LogPending(query_id=query_id)
        if status in QUERY_TERMINAL_FAILURES:
            raise Upstream(f"log query {status.lower()}")

        return LogRows(rows=[log_row_of(row) for row in response["results"]])


def int_of(value: object) -> int:
    match value:
        case int():
            return value
        case str() if value.isdigit():
            return int(value)
        case _:
            return 0


def matches_local_filters(
    record: Mapping[str, object], account_id: str, filters: LogFilters
) -> bool:
    if record.get("event") != "api_request" or record.get("account_id") != account_id:
        return False
    if filters.outcome is not None and record.get("outcome") != filters.outcome:
        return False
    if filters.route is not None and record.get("route") != filters.route:
        return False
    return filters.user_id is None or record.get("user_id") == filters.user_id


def local_timestamp_in(record: Mapping[str, object], window: LogWindow) -> datetime | None:
    raw_timestamp = record.get("ts")
    if not isinstance(raw_timestamp, str):
        return None
    try:
        timestamp = datetime.fromisoformat(raw_timestamp)
    except ValueError:
        return None

    since, until = window
    return timestamp if since <= timestamp <= until else None


def local_log_row(
    record: Mapping[str, object], account_id: str, filters: LogFilters, window: LogWindow
) -> LogRow | None:
    if not matches_local_filters(record, account_id, filters):
        return None

    timestamp = local_timestamp_in(record, window)
    if timestamp is None:
        return None

    return LogRow(
        latency_ms=int_of(record.get("latency_ms")),
        method=str(record.get("method", "")),
        outcome=str(record.get("outcome", "")),
        request_id=str(record.get("request_id", "")),
        route=str(record.get("route", "")),
        status=int_of(record.get("status")),
        timestamp=timestamp,
        user_id=str(record.get("user_id", "")),
    )


@dataclass(frozen=True, slots=True)
class LocalLogQueries:
    path: Path
    pending: dict[str, tuple[str, LogFilters, LogWindow]] = field(default_factory=dict)

    async def start(self, account_id: str, filters: LogFilters, window: LogWindow) -> str:
        query_id = str(uuid.uuid7())
        self.pending[query_id] = (account_id, filters, window)
        return query_id

    async def poll(self, query_id: str) -> LogResult:
        account_id, filters, window = self.pending.pop(query_id)
        if not self.path.exists():
            return LogRows(rows=[])

        rows = [
            row
            for line in self.path.read_text().splitlines()
            if (row := self._parsed(line, account_id, filters, window)) is not None
        ]
        rows.sort(key=lambda row: row.timestamp, reverse=True)
        return LogRows(rows=rows[:QUERY_ROW_LIMIT])

    def _parsed(
        self, line: str, account_id: str, filters: LogFilters, window: LogWindow
    ) -> LogRow | None:
        try:
            record = json.loads(line)
        except ValueError:
            return None

        return (
            local_log_row(record, account_id, filters, window) if isinstance(record, dict) else None
        )

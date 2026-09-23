import asyncio
import itertools
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from txtlocal.shared.errors import Internal
from txtlocal.shared.money import Micro
from txtlocal.shared.table import (
    METADATA_SK,
    Table,
    backoff,
    condition_failed_as_false,
    key,
    n,
    paged_items,
    partition,
    s,
    sort_ts,
)
from txtlocal.slices.analytics.model import (
    ClickDay,
    RollupFeed,
    TrackedLink,
    UsageLine,
    is_valid_code,
)
from txtlocal.slices.messaging.model import Product

if TYPE_CHECKING:
    from types_aiobotocore_athena import AthenaClient
    from types_aiobotocore_athena.type_defs import RowTypeDef
    from types_aiobotocore_dynamodb.type_defs import AttributeValueTypeDef, QueryInputTypeDef
    from types_aiobotocore_logs import CloudWatchLogsClient
    from types_aiobotocore_logs.type_defs import ResultFieldTypeDef

ATHENA_DATABASE = "aws_cloud"
ATHENA_MAX_PAGES = 200
ATHENA_PENDING_STATES = frozenset({"QUEUED", "RUNNING"})
ATHENA_ROW_COLUMNS = 2
ATHENA_TERMINAL_FAILURES = frozenset({"CANCELLED", "FAILED"})

BATCH_GET_LEFTOVERS_MESSAGE = "a batch read of link days did not finish after 8 rounds"
BATCH_GET_SIZE = 100
MAX_BATCH_GET_ROUNDS = 8

CAMPAIGN_LINKS_INDEX = "GSI1"
DAY_PREFIX = "DAY#"
FEED_PREFIX = "FEED#"
LINK = "LINK"
ROLLUP = "ROLLUP"
STEM_PREFIX = "/l/"
USAGE = "USAGE"
SORT_KEY_CEILING = "~"

PAGE_CAP = 12
LINKS_PAGE_CAP_EXCEEDED = "the campaign links read more pages than their cap"
USAGE_PAGE_CAP_EXCEEDED = "the usage month read more pages than its cap"

BY_CAMPAIGN = "GSI1PK = :pk"
BY_MONTH = "PK = :pk"
BY_MONTH_AND_DAYS = "PK = :pk AND SK BETWEEN :since AND :until"
IF_ABSENT = "attribute_not_exists(PK)"
ROLLUP_ONCE_PER_DAY = (
    "attribute_exists(PK) AND (attribute_not_exists(lastRollup) OR lastRollup < :day)"
)

LINK_DAY_TTL = timedelta(days=90)
LINK_TTL = timedelta(days=400)
ROLLUP_MARKER_TTL = timedelta(days=400)
USAGE_TTL = timedelta(days=400)

INSIGHTS_PENDING_STATUSES = frozenset({"Scheduled", "Running"})
INSIGHTS_TERMINAL_FAILURES = frozenset({"Cancelled", "Failed", "Timeout", "Unknown"})

USAGE_QUERY = (
    "fields account_id, user_id, product, sender_id, country, price_micro\n"
    '| filter event = "message_accepted"\n'
    "| stats count() as quantity, sum(price_micro) as cost_micro\n"
    "    by account_id, user_id, product, sender_id, country"
)


def expires_at(moment: datetime, ttl: timedelta) -> int:
    return int((moment + ttl).timestamp())


def epoch_seconds(moment: datetime) -> int:
    return int(moment.timestamp())


def day_bounds(day: date) -> tuple[int, int]:
    start = datetime(day.year, day.month, day.day, tzinfo=UTC)
    return epoch_seconds(start), epoch_seconds(start + timedelta(days=1))


def month_of(day: str) -> str:
    return day[:7]


def clicks_query(day: date, host: str) -> str:
    return (
        "SELECT cs_uri_stem, count(*) AS clicks\n"
        f'FROM "{ATHENA_DATABASE}"."cloudfront_logs"\n'
        f"WHERE year = {day.year} AND month = {day.month:02d} AND day = {day.day:02d}\n"
        f"  AND x_host_header = '{host}'\n"
        "  AND cs_uri_stem LIKE '/l/%'\n"
        "  AND sc_status = 302\n"
        "GROUP BY 1"
    )


def text_of(item: Mapping[str, AttributeValueTypeDef], field_name: str) -> str:
    match item.get(field_name):
        case {"S": str(value)}:
            return value
        case _:
            raise Internal(f"{field_name} missing or malformed")


def optional_text_of(item: Mapping[str, AttributeValueTypeDef], field_name: str) -> str | None:
    match item.get(field_name):
        case {"S": str(value)}:
            return value
        case _:
            return None


def int_of(item: Mapping[str, AttributeValueTypeDef], field_name: str) -> int:
    match item.get(field_name):
        case {"N": str(value)}:
            return int(value)
        case _:
            raise Internal(f"{field_name} missing or malformed")


def link_key(code: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(LINK, code), METADATA_SK)


def link_day_key(code: str, day: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(LINK, code), f"{DAY_PREFIX}{day}")


def rollup_marker_key(day: str, feed: RollupFeed) -> dict[str, AttributeValueTypeDef]:
    return key(partition(ROLLUP, day), f"{FEED_PREFIX}{feed}")


def usage_partition(account_id: str, month: str) -> str:
    return partition(USAGE, f"{account_id}#{month}")


def usage_sort_key(line: UsageLine) -> str:
    return f"{line.day}#{line.product}#{line.user_id}#{line.sender_id}#{line.country}"


def campaign_links_partition(campaign_id: str) -> str:
    return partition("CAMPAIGN", f"{campaign_id}#LINKS")


def link_item(link: TrackedLink) -> dict[str, AttributeValueTypeDef]:
    item: dict[str, AttributeValueTypeDef] = {
        **link_key(link.code),
        "GSI1PK": s(campaign_links_partition(link.campaign_id)),
        "GSI1SK": s(f"{sort_ts(link.created_at)}#{link.code}"),
        "accountId": s(link.account_id),
        "campaignId": s(link.campaign_id),
        "clicksTotal": n(link.clicks_total),
        "createdAt": s(sort_ts(link.created_at)),
        "ttl": n(expires_at(link.created_at, LINK_TTL)),
        "url": s(link.url),
    }
    if link.last_rollup is not None:
        item["lastRollup"] = s(link.last_rollup)
    return item


def link_of(item: Mapping[str, AttributeValueTypeDef]) -> TrackedLink:
    return TrackedLink(
        account_id=text_of(item, "accountId"),
        campaign_id=text_of(item, "campaignId"),
        clicks_total=int_of(item, "clicksTotal"),
        code=text_of(item, "PK").removeprefix(partition(LINK, "")),
        created_at=datetime.fromisoformat(text_of(item, "createdAt")),
        last_rollup=optional_text_of(item, "lastRollup"),
        url=text_of(item, "url"),
    )


def usage_line_of(account_id: str, item: Mapping[str, AttributeValueTypeDef]) -> UsageLine:
    return UsageLine(
        account_id=account_id,
        cost_micro=Micro(int_of(item, "costMicro")),
        country=text_of(item, "country"),
        day=text_of(item, "date"),
        product=Product(text_of(item, "product")),
        quantity=int_of(item, "quantity"),
        sender_id=text_of(item, "senderId"),
        user_id=text_of(item, "userId"),
    )


class AnalyticsRepo(Protocol):
    async def add_clicks_total(self, code: str, day: str, clicks: int) -> bool: ...

    async def claim_rollup_marker(self, day: str, feed: RollupFeed, now: datetime) -> bool: ...

    async def clear_rollup_marker(self, day: str, feed: RollupFeed) -> None: ...

    async def get_link(self, code: str) -> TrackedLink | None: ...

    async def link_days(
        self, codes: Sequence[str], since: date, until: date
    ) -> dict[str, dict[str, int]]: ...

    async def links_of_campaign(self, campaign_id: str) -> list[TrackedLink]: ...

    async def put_link(self, link: TrackedLink) -> bool: ...

    async def put_link_day(self, code: str, day: str, clicks: int, now: datetime) -> None: ...

    async def put_usage_row(self, line: UsageLine, now: datetime) -> None: ...

    async def usage_of_month(
        self,
        account_id: str,
        month: str,
        since_day: str | None = None,
        until_day: str | None = None,
    ) -> list[UsageLine]: ...


@dataclass(frozen=True, slots=True)
class AnalyticsDynamoRepo:
    table: Table

    async def put_link(self, link: TrackedLink) -> bool:
        return await condition_failed_as_false(self.table.client.put_item)(
            ConditionExpression=IF_ABSENT, Item=link_item(link), TableName=self.table.name
        )

    async def get_link(self, code: str) -> TrackedLink | None:
        response = await self.table.client.get_item(Key=link_key(code), TableName=self.table.name)
        item = response.get("Item")
        return None if item is None else link_of(item)

    async def links_of_campaign(self, campaign_id: str) -> list[TrackedLink]:
        request: QueryInputTypeDef = {
            "ExpressionAttributeValues": {":pk": s(campaign_links_partition(campaign_id))},
            "IndexName": CAMPAIGN_LINKS_INDEX,
            "KeyConditionExpression": BY_CAMPAIGN,
            "TableName": self.table.name,
        }

        items = await paged_items(self.table.client, request, PAGE_CAP, LINKS_PAGE_CAP_EXCEEDED)
        return [link_of(item) for item in items]

    async def put_link_day(self, code: str, day: str, clicks: int, now: datetime) -> None:
        await self.table.client.put_item(
            Item={
                **link_day_key(code, day),
                "clicks": n(clicks),
                "date": s(day),
                "ttl": n(expires_at(now, LINK_DAY_TTL)),
            },
            TableName=self.table.name,
        )

    async def add_clicks_total(self, code: str, day: str, clicks: int) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=ROLLUP_ONCE_PER_DAY,
            ExpressionAttributeValues={":clicks": n(clicks), ":day": s(day)},
            Key=link_key(code),
            TableName=self.table.name,
            UpdateExpression="ADD clicksTotal :clicks SET lastRollup = :day",
        )

    async def link_days(
        self, codes: Sequence[str], since: date, until: date
    ) -> dict[str, dict[str, int]]:
        span = (until - since).days + 1
        days = [(since + timedelta(days=offset)).isoformat() for offset in range(span)]
        keys = [link_day_key(code, day) for code in codes for day in days]

        result: dict[str, dict[str, int]] = {code: {} for code in codes}
        prefix = partition(LINK, "")
        for item in await self._batch_get(keys):
            code = text_of(item, "PK").removeprefix(prefix)
            day = text_of(item, "SK").removeprefix(DAY_PREFIX)
            result[code][day] = int_of(item, "clicks")
        return result

    async def put_usage_row(self, line: UsageLine, now: datetime) -> None:
        await self.table.client.put_item(
            Item={
                **key(usage_partition(line.account_id, month_of(line.day)), usage_sort_key(line)),
                "costMicro": n(line.cost_micro),
                "country": s(line.country),
                "date": s(line.day),
                "product": s(line.product),
                "quantity": n(line.quantity),
                "senderId": s(line.sender_id),
                "ttl": n(expires_at(now, USAGE_TTL)),
                "userId": s(line.user_id),
            },
            TableName=self.table.name,
        )

    async def usage_of_month(
        self,
        account_id: str,
        month: str,
        since_day: str | None = None,
        until_day: str | None = None,
    ) -> list[UsageLine]:
        values: dict[str, AttributeValueTypeDef] = {":pk": s(usage_partition(account_id, month))}
        condition = BY_MONTH
        if since_day is not None and until_day is not None:
            values[":since"] = s(since_day)
            values[":until"] = s(f"{until_day}{SORT_KEY_CEILING}")
            condition = BY_MONTH_AND_DAYS

        request: QueryInputTypeDef = {
            "ExpressionAttributeValues": values,
            "KeyConditionExpression": condition,
            "TableName": self.table.name,
        }

        items = await paged_items(self.table.client, request, PAGE_CAP, USAGE_PAGE_CAP_EXCEEDED)
        return [usage_line_of(account_id, item) for item in items]

    async def claim_rollup_marker(self, day: str, feed: RollupFeed, now: datetime) -> bool:
        return await condition_failed_as_false(self.table.client.put_item)(
            ConditionExpression=IF_ABSENT,
            Item={**rollup_marker_key(day, feed), "ttl": n(expires_at(now, ROLLUP_MARKER_TTL))},
            TableName=self.table.name,
        )

    async def clear_rollup_marker(self, day: str, feed: RollupFeed) -> None:
        await self.table.client.delete_item(
            Key=rollup_marker_key(day, feed), TableName=self.table.name
        )

    async def _batch_get(
        self, keys: Sequence[dict[str, AttributeValueTypeDef]]
    ) -> list[dict[str, AttributeValueTypeDef]]:
        items: list[dict[str, AttributeValueTypeDef]] = []
        for chunk in itertools.batched(keys, BATCH_GET_SIZE, strict=False):
            items.extend(await self._batch_get_chunk(list(chunk)))
        return items

    async def _batch_get_chunk(
        self, keys: list[dict[str, AttributeValueTypeDef]]
    ) -> list[dict[str, AttributeValueTypeDef]]:
        pending = keys
        items: list[dict[str, AttributeValueTypeDef]] = []
        for attempt in range(MAX_BATCH_GET_ROUNDS):
            response = await self.table.client.batch_get_item(
                RequestItems={self.table.name: {"Keys": pending}}
            )
            items.extend(response["Responses"][self.table.name])

            unprocessed = response.get("UnprocessedKeys", {}).get(self.table.name)
            if unprocessed is None or not unprocessed["Keys"]:
                return items
            pending = list(unprocessed["Keys"])
            await asyncio.sleep(backoff(attempt))

        raise Internal(BATCH_GET_LEFTOVERS_MESSAGE)


@dataclass(frozen=True, slots=True)
class UsagePending:
    query_id: str


@dataclass(frozen=True, slots=True)
class UsageRows:
    discarded: int
    rows: list[UsageLine]


type UsageResult = UsagePending | UsageRows


class UsageQueries(Protocol):
    async def start(self, day: date) -> str: ...

    async def poll(self, query_id: str) -> UsageResult: ...


@dataclass(frozen=True, slots=True)
class ClickPending:
    query_id: str


@dataclass(frozen=True, slots=True)
class ClickRows:
    discarded: int
    rows: list[ClickDay]


type ClickResult = ClickPending | ClickRows


class ClickQueries(Protocol):
    async def start(self, day: date) -> str: ...

    async def poll(self, query_id: str) -> ClickResult: ...


def usage_line_of_fields(fields: Sequence[ResultFieldTypeDef], day: str) -> UsageLine | None:
    values = {one["field"]: one["value"] for one in fields if "field" in one and "value" in one}
    try:
        return UsageLine(
            account_id=values["account_id"],
            cost_micro=Micro(int(values["cost_micro"])),
            country=values["country"],
            day=day,
            product=Product(values["product"]),
            quantity=int(values["quantity"]),
            sender_id=values["sender_id"],
            user_id=values["user_id"],
        )
    except KeyError, ValueError:
        return None


@dataclass(frozen=True, slots=True)
class InsightsUsageQueries:
    log_group: str
    logs_client: CloudWatchLogsClient
    pending: dict[str, str] = field(default_factory=dict)

    async def start(self, day: date) -> str:
        start, end = day_bounds(day)
        response = await self.logs_client.start_query(
            endTime=end, logGroupName=self.log_group, queryString=USAGE_QUERY, startTime=start
        )
        query_id = response["queryId"]
        self.pending[query_id] = day.isoformat()
        return query_id

    async def poll(self, query_id: str) -> UsageResult:
        response = await self.logs_client.get_query_results(queryId=query_id)
        status = response["status"]
        if status in INSIGHTS_PENDING_STATUSES:
            return UsagePending(query_id=query_id)
        if status in INSIGHTS_TERMINAL_FAILURES:
            raise Internal(f"usage query {status.lower()}")

        day = self.pending.pop(query_id, "")
        parsed = [usage_line_of_fields(row, day) for row in response["results"]]
        lines = [line for line in parsed if line is not None]
        return UsageRows(discarded=len(parsed) - len(lines), rows=lines)


def code_of_stem(stem: str) -> str | None:
    return stem.removeprefix(STEM_PREFIX) if stem.startswith(STEM_PREFIX) else None


def click_day_of_row(row: RowTypeDef, day: str) -> ClickDay | None:
    data = row.get("Data", [])
    if len(data) < ATHENA_ROW_COLUMNS:
        return None

    stem = data[0].get("VarCharValue")
    count = data[1].get("VarCharValue")
    if stem is None or count is None or not count.isdigit():
        return None

    code = code_of_stem(stem)
    if code is None or not is_valid_code(code):
        return None
    return ClickDay(clicks=int(count), code=code, day=day)


@dataclass(frozen=True, slots=True)
class AthenaClickQueries:
    athena_client: AthenaClient
    host: str
    output: str
    workgroup: str
    pending: dict[str, str] = field(default_factory=dict)

    async def start(self, day: date) -> str:
        response = await self.athena_client.start_query_execution(
            QueryExecutionContext={"Database": ATHENA_DATABASE},
            QueryString=clicks_query(day, self.host),
            ResultConfiguration={"OutputLocation": self.output},
            WorkGroup=self.workgroup,
        )
        query_id = response["QueryExecutionId"]
        self.pending[query_id] = day.isoformat()
        return query_id

    async def poll(self, query_id: str) -> ClickResult:
        execution = await self.athena_client.get_query_execution(QueryExecutionId=query_id)
        state = execution["QueryExecution"]["Status"]["State"]
        if state in ATHENA_PENDING_STATES:
            return ClickPending(query_id=query_id)
        if state in ATHENA_TERMINAL_FAILURES:
            raise Internal(f"click query {state.lower()}")

        day = self.pending.pop(query_id, "")
        rows: list[ClickDay] = []
        discarded = 0
        page_number = 0
        paginator = self.athena_client.get_paginator("get_query_results")
        async for page in paginator.paginate(QueryExecutionId=query_id):
            data_rows = page["ResultSet"]["Rows"]
            for row in data_rows[1:] if page_number == 0 else data_rows:
                parsed = click_day_of_row(row, day)
                if parsed is None:
                    discarded += 1
                else:
                    rows.append(parsed)

            page_number += 1
            if page_number >= ATHENA_MAX_PAGES:
                break

        return ClickRows(discarded=discarded, rows=rows)


def _json_object(line: str) -> Mapping[str, object] | None:
    try:
        record = json.loads(line)
    except ValueError:
        return None
    return record if isinstance(record, dict) else None


def _usage_group_of(record: Mapping[str, object]) -> tuple[str, str, Product, str, str] | None:
    try:
        return (
            str(record["account_id"]),
            str(record["user_id"]),
            Product(str(record["product"])),
            str(record["sender_id"]),
            str(record["country"]),
        )
    except KeyError, ValueError:
        return None


def _within_day(record: Mapping[str, object], day: date) -> bool:
    raw_ts = record.get("ts")
    if not isinstance(raw_ts, str):
        return False
    try:
        timestamp = datetime.fromisoformat(raw_ts)
    except ValueError:
        return False
    return timestamp.date() == day


@dataclass(frozen=True, slots=True)
class LocalUsageQueries:
    path: Path
    pending: dict[str, date] = field(default_factory=dict)

    async def start(self, day: date) -> str:
        query_id = str(uuid.uuid7())
        self.pending[query_id] = day
        return query_id

    async def poll(self, query_id: str) -> UsageResult:
        day = self.pending.pop(query_id)
        if not self.path.exists():
            return UsageRows(discarded=0, rows=[])

        totals: dict[tuple[str, str, Product, str, str], list[int]] = {}
        discarded = 0
        for line in self.path.read_text().splitlines():
            record = _json_object(line)
            if record is None or record.get("event") != "message_accepted":
                continue
            if not _within_day(record, day):
                continue

            group = _usage_group_of(record)
            price = record.get("price_micro")
            if group is None or not isinstance(price, int):
                discarded += 1
                continue

            counted = totals.setdefault(group, [0, 0])
            counted[0] += 1
            counted[1] += price

        rows = [
            UsageLine(
                account_id=account_id,
                cost_micro=Micro(cost_micro),
                country=country,
                day=day.isoformat(),
                product=product,
                quantity=quantity,
                sender_id=sender_id,
                user_id=user_id,
            )
            for (account_id, user_id, product, sender_id, country), (
                quantity,
                cost_micro,
            ) in totals.items()
        ]
        return UsageRows(discarded=discarded, rows=rows)


@dataclass(frozen=True, slots=True)
class LocalClickQueries:
    path: Path
    pending: dict[str, date] = field(default_factory=dict)

    async def start(self, day: date) -> str:
        query_id = str(uuid.uuid7())
        self.pending[query_id] = day
        return query_id

    async def poll(self, query_id: str) -> ClickResult:
        day = self.pending.pop(query_id)
        if not self.path.exists():
            return ClickRows(discarded=0, rows=[])

        counts: dict[str, int] = {}
        discarded = 0
        for line in self.path.read_text().splitlines():
            record = _json_object(line)
            if (
                record is None
                or record.get("event") != "redirect_hit"
                or record.get("hit") is not True
            ):
                continue
            if not _within_day(record, day):
                continue

            code = record.get("code")
            if not isinstance(code, str) or not is_valid_code(code):
                discarded += 1
                continue
            counts[code] = counts.get(code, 0) + 1

        rows = [
            ClickDay(clicks=count, code=code, day=day.isoformat()) for code, count in counts.items()
        ]
        return ClickRows(discarded=discarded, rows=rows)

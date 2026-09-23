import functools
import secrets
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from random import Random
from typing import TYPE_CHECKING

from botocore.exceptions import ClientError

from txtlocal.shared.errors import Internal

if TYPE_CHECKING:
    from types_aiobotocore_dynamodb import DynamoDBClient
    from types_aiobotocore_dynamodb.type_defs import AttributeValueTypeDef, QueryInputTypeDef

APP = "txtlocal"
METADATA_SK = "#METADATA"
PLATFORM = f"{APP}#PLATFORM"
BACKOFF_BASE_SECONDS = 0.05
BACKOFF_CAP_SECONDS = 3.0
BACKOFF_EXPONENT_CAP = 6
CONDITION_FAILED = "ConditionalCheckFailedException"
TRANSACTION_CANCELLED = "TransactionCanceledException"
CANCELLED_BY_CONDITION = "ConditionalCheckFailed"
BY_PREFIX = "PK = :pk AND begins_with(SK, :prefix)"
IF_PRESENT = "attribute_exists(PK)"
UNSUPPORTED_ATTRIBUTE = "unsupported attribute value"

_system_random = secrets.SystemRandom()


@dataclass(frozen=True, slots=True)
class Table:
    client: DynamoDBClient
    name: str


def partition(kind: str, ident: str) -> str:
    return f"{APP}#{kind}#{ident}"


def sort_ts(moment: datetime) -> str:
    utc = moment.astimezone(UTC)
    return f"{utc:%Y-%m-%dT%H:%M:%S}.{utc.microsecond // 1000:03d}Z"


def backoff(attempt: int, rng: Random = _system_random) -> float:
    ceiling = min(
        BACKOFF_CAP_SECONDS, BACKOFF_BASE_SECONDS * 2.0 ** min(attempt, BACKOFF_EXPONENT_CAP)
    )
    return ceiling * rng.random()


def s(value: str) -> AttributeValueTypeDef:
    return {"S": value}


def n(value: int) -> AttributeValueTypeDef:
    return {"N": str(value)}


def key(pk: str, sk: str) -> dict[str, AttributeValueTypeDef]:
    return {"PK": s(pk), "SK": s(sk)}


def plain(value: AttributeValueTypeDef) -> object:
    match value:
        case {"BOOL": bool(flag)}:
            return flag
        case {"N": str(number)}:
            return int(number)
        case {"S": str(text)}:
            return text
        case {"L": list(entries)}:
            return [plain(entry) for entry in entries]
        case {"M": dict(fields)}:
            return {name: plain(entry) for name, entry in fields.items()}
    raise Internal(UNSUPPORTED_ATTRIBUTE)


def error_code(error: ClientError) -> str:
    response: Mapping[str, object] = error.response
    details = response.get("Error")
    if not isinstance(details, dict):
        return "Unknown"
    return str(details.get("Code", "Unknown"))


def cancellation_reasons(error: ClientError) -> list[str]:
    response: Mapping[str, object] = error.response
    reasons = response.get("CancellationReasons")
    if not isinstance(reasons, list):
        return []
    return [str(reason.get("Code", "")) for reason in reasons if isinstance(reason, dict)]


def is_condition_failed(error: ClientError) -> bool:
    code = error_code(error)
    if code == CONDITION_FAILED:
        return True
    if code != TRANSACTION_CANCELLED:
        return False
    return CANCELLED_BY_CONDITION in cancellation_reasons(error)


async def paged_items(
    client: DynamoDBClient, request: QueryInputTypeDef, cap: int, exhausted: str
) -> list[dict[str, AttributeValueTypeDef]]:
    items: list[dict[str, AttributeValueTypeDef]] = []
    for _ in range(cap):
        response = await client.query(**request)
        items.extend(response.get("Items", []))

        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return items
        request["ExclusiveStartKey"] = last_key

    raise Internal(exhausted)


def condition_failed_as_false[**P](
    write: Callable[P, Awaitable[object]],
) -> Callable[P, Awaitable[bool]]:
    @functools.wraps(write)
    async def guarded(*args: P.args, **kwargs: P.kwargs) -> bool:
        try:
            await write(*args, **kwargs)
        except ClientError as error:
            if is_condition_failed(error):
                return False
            raise Internal(error_code(error)) from error
        return True

    return guarded


async def prefix_items(
    table: Table, pk: str, prefix: str, cap: int, exhausted: str
) -> list[dict[str, AttributeValueTypeDef]]:
    request: QueryInputTypeDef = {
        "ExpressionAttributeValues": {":pk": s(pk), ":prefix": s(prefix)},
        "KeyConditionExpression": BY_PREFIX,
        "TableName": table.name,
    }
    return await paged_items(table.client, request, cap, exhausted)


async def delete_if_present(table: Table, item_key: dict[str, AttributeValueTypeDef]) -> bool:
    return await condition_failed_as_false(table.client.delete_item)(
        ConditionExpression=IF_PRESENT, Key=item_key, TableName=table.name
    )

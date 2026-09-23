from datetime import UTC, datetime
from random import Random
from typing import Any, cast

import pytest
from botocore.exceptions import ClientError

from txtlocal.shared.errors import INTERNAL_MESSAGE, Internal
from txtlocal.shared.table import (
    BACKOFF_BASE_SECONDS,
    BACKOFF_CAP_SECONDS,
    backoff,
    condition_failed_as_false,
    key,
    n,
    partition,
    s,
    sort_ts,
)

SAMPLES = 1000


def client_error(code: str, reasons: list[str] | None = None) -> ClientError:
    response: dict[str, object] = {"Error": {"Code": code, "Message": code}}
    if reasons is not None:
        response["CancellationReasons"] = [{"Code": reason} for reason in reasons]
    return ClientError(cast("Any", response), "PutItem")


def test_partition_carries_the_app_prefix() -> None:
    assert partition("ACCOUNT", "abc") == "txtlocal#ACCOUNT#abc"


def test_sort_ts_is_rfc3339_millis_in_utc() -> None:
    moment = datetime(2026, 9, 19, 12, 30, 45, 123_999, tzinfo=UTC)
    assert sort_ts(moment) == "2026-09-19T12:30:45.123Z"


def test_attribute_helpers() -> None:
    assert key("pk", "sk") == {"PK": {"S": "pk"}, "SK": {"S": "sk"}}
    assert s("x") == {"S": "x"}
    assert n(7) == {"N": "7"}


@pytest.mark.parametrize(
    ("attempt", "ceiling"),
    [(0, BACKOFF_BASE_SECONDS), (3, BACKOFF_BASE_SECONDS * 8), (20, BACKOFF_CAP_SECONDS)],
    ids=["first-attempt", "doubles", "capped"],
)
def test_backoff_is_full_jitter_under_its_ceiling(attempt: int, ceiling: float) -> None:
    rng = Random(42)
    samples = [backoff(attempt, rng) for _ in range(SAMPLES)]
    assert min(samples) >= 0
    assert max(samples) < ceiling
    assert max(samples) > ceiling * 0.9


async def test_condition_failed_as_false_passes_a_successful_write() -> None:
    @condition_failed_as_false
    async def write() -> None:
        return None

    assert await write() is True


@pytest.mark.parametrize(
    "error",
    [
        client_error("ConditionalCheckFailedException"),
        client_error("TransactionCanceledException", ["None", "ConditionalCheckFailed"]),
    ],
    ids=["single-item-condition", "transaction-with-a-failed-condition"],
)
async def test_condition_failed_as_false_maps_a_lost_condition(error: ClientError) -> None:
    @condition_failed_as_false
    async def write() -> None:
        raise error

    assert await write() is False


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (
            client_error("ProvisionedThroughputExceededException"),
            "ProvisionedThroughputExceededException",
        ),
        (
            client_error("TransactionCanceledException", ["TransactionConflict"]),
            "TransactionCanceledException",
        ),
    ],
    ids=["throttle", "transaction-conflict-is-not-a-lost-condition"],
)
async def test_condition_failed_as_false_raises_internal_for_anything_else(
    error: ClientError, code: str
) -> None:
    @condition_failed_as_false
    async def write() -> None:
        raise error

    with pytest.raises(Internal) as caught:
        await write()
    assert str(caught.value) == code
    assert caught.value.public_message() == INTERNAL_MESSAGE

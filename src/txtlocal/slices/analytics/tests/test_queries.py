import json
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from txtlocal.shared.money import Micro
from txtlocal.slices.analytics.model import ClickDay, UsageLine
from txtlocal.slices.analytics.repo import (
    USAGE_QUERY,
    ClickRows,
    LocalClickQueries,
    LocalUsageQueries,
    UsageRows,
    click_day_of_row,
    clicks_query,
    usage_line_of_fields,
)
from txtlocal.slices.messaging.model import Product
from txtlocal.slices.messaging.service import MessageAccepted

if TYPE_CHECKING:
    from types_aiobotocore_athena.type_defs import RowTypeDef
    from types_aiobotocore_logs.type_defs import ResultFieldTypeDef

USAGE_QUERY_FIELDS = {"account_id", "user_id", "product", "sender_id", "country", "price_micro"}


def test_usage_query_only_groups_by_fields_the_emitter_actually_sends() -> None:
    assert set(MessageAccepted.__annotations__) >= USAGE_QUERY_FIELDS


def test_usage_query_text() -> None:
    assert USAGE_QUERY == (
        "fields account_id, user_id, product, sender_id, country, price_micro\n"
        '| filter event = "message_accepted"\n'
        "| stats count() as quantity, sum(price_micro) as cost_micro\n"
        "    by account_id, user_id, product, sender_id, country"
    )


def test_clicks_query_text() -> None:
    query = clicks_query(date(2026, 9, 18), "app.txtlocal.example")
    assert query == (
        "SELECT cs_uri_stem, count(*) AS clicks\n"
        'FROM "aws_cloud"."cloudfront_logs"\n'
        "WHERE year = 2026 AND month = 09 AND day = 18\n"
        "  AND x_host_header = 'app.txtlocal.example'\n"
        "  AND cs_uri_stem LIKE '/l/%'\n"
        "  AND sc_status = 302\n"
        "GROUP BY 1"
    )


def field_row(**values: str) -> list[ResultFieldTypeDef]:
    return [{"field": name, "value": value} for name, value in values.items()]


def test_usage_line_of_fields_parses_a_complete_row() -> None:
    row = field_row(
        account_id="acc-1",
        user_id="usr-1",
        product="SMS",
        sender_id="snd-1",
        country="GB",
        quantity="3",
        cost_micro="128100",
    )

    line = usage_line_of_fields(row, "2026-09-18")

    assert line == UsageLine(
        account_id="acc-1",
        cost_micro=Micro(128100),
        country="GB",
        day="2026-09-18",
        product=Product.SMS,
        quantity=3,
        sender_id="snd-1",
        user_id="usr-1",
    )


def test_usage_line_of_fields_discards_a_row_missing_a_field() -> None:
    row = field_row(account_id="acc-1", user_id="usr-1", product="SMS")
    assert usage_line_of_fields(row, "2026-09-18") is None


def click_row(stem: str, clicks: str) -> RowTypeDef:
    return {"Data": [{"VarCharValue": stem}, {"VarCharValue": clicks}]}


def test_click_day_of_row_parses_a_valid_stem() -> None:
    parsed = click_day_of_row(click_row("/l/ab3de5fgh7", "4"), "2026-09-18")
    assert parsed == ClickDay(clicks=4, code="ab3de5fgh7", day="2026-09-18")


def test_click_day_of_row_discards_a_code_that_fails_the_alphabet_check() -> None:
    assert click_day_of_row(click_row("/l/AB3DE5FGH7", "4"), "2026-09-18") is None


def test_click_day_of_row_discards_a_stem_outside_the_link_prefix() -> None:
    assert click_day_of_row(click_row("/other/path", "4"), "2026-09-18") is None


def usage_line(account_id: str, price_micro: int, **extra: object) -> dict[str, object]:
    return {
        "event": "message_accepted",
        "ts": "2026-09-18T12:00:00.000+00:00",
        "account_id": account_id,
        "user_id": "usr-1",
        "product": "SMS",
        "sender_id": "snd-1",
        "country": "GB",
        "price_micro": price_micro,
        **extra,
    }


async def test_local_usage_queries_sums_quantity_and_cost_by_group(tmp_path: Path) -> None:
    log_file = tmp_path / "api.log"
    lines = [
        usage_line("acc-1", 42700),
        usage_line("acc-1", 42700),
        {"event": "api_request", "account_id": "acc-1"},
    ]
    log_file.write_text("\n".join(json.dumps(line) for line in lines))

    queries = LocalUsageQueries(path=log_file)
    result = await queries.poll(await queries.start(date(2026, 9, 18)))

    assert isinstance(result, UsageRows)
    assert result.discarded == 0
    assert result.rows == [
        UsageLine(
            account_id="acc-1",
            cost_micro=Micro(85400),
            country="GB",
            day="2026-09-18",
            product=Product.SMS,
            quantity=2,
            sender_id="snd-1",
            user_id="usr-1",
        )
    ]


async def test_local_usage_queries_discards_a_line_missing_price(tmp_path: Path) -> None:
    log_file = tmp_path / "api.log"
    malformed = usage_line("acc-1", 0)
    del malformed["price_micro"]
    log_file.write_text(json.dumps(malformed))

    queries = LocalUsageQueries(path=log_file)
    result = await queries.poll(await queries.start(date(2026, 9, 18)))

    assert isinstance(result, UsageRows)
    assert (result.discarded, result.rows) == (1, [])


async def test_local_usage_queries_answers_empty_when_the_log_file_is_absent(
    tmp_path: Path,
) -> None:
    queries = LocalUsageQueries(path=tmp_path / "missing.log")
    result = await queries.poll(await queries.start(date(2026, 9, 18)))

    assert isinstance(result, UsageRows)
    assert (result.discarded, result.rows) == (0, [])


async def test_local_usage_queries_excludes_a_line_from_a_different_day(tmp_path: Path) -> None:
    log_file = tmp_path / "api.log"
    other_day = usage_line("acc-1", 42700, ts="2026-09-17T23:59:00.000+00:00")
    log_file.write_text(json.dumps(other_day))

    queries = LocalUsageQueries(path=log_file)
    result = await queries.poll(await queries.start(date(2026, 9, 18)))

    assert isinstance(result, UsageRows)
    assert (result.discarded, result.rows) == (0, [])


async def test_local_click_queries_counts_only_hits(tmp_path: Path) -> None:
    log_file = tmp_path / "api.log"
    lines = [
        {
            "event": "redirect_hit",
            "ts": "2026-09-18T12:00:00.000+00:00",
            "code": "ab3de5fgh7",
            "hit": True,
        },
        {
            "event": "redirect_hit",
            "ts": "2026-09-18T12:00:00.000+00:00",
            "code": "ab3de5fgh7",
            "hit": True,
        },
        {
            "event": "redirect_hit",
            "ts": "2026-09-18T12:00:00.000+00:00",
            "code": "zz9zz9zz99",
            "hit": False,
        },
        {"event": "message_accepted", "ts": "2026-09-18T12:00:00.000+00:00", "code": "ab3de5fgh7"},
    ]
    log_file.write_text("\n".join(json.dumps(line) for line in lines))

    queries = LocalClickQueries(path=log_file)
    result = await queries.poll(await queries.start(date(2026, 9, 18)))

    assert isinstance(result, ClickRows)
    assert result.discarded == 0
    assert result.rows == [ClickDay(clicks=2, code="ab3de5fgh7", day="2026-09-18")]


async def test_local_click_queries_discards_an_invalid_code_on_a_hit(tmp_path: Path) -> None:
    log_file = tmp_path / "api.log"
    log_file.write_text(
        json.dumps(
            {
                "event": "redirect_hit",
                "ts": "2026-09-18T12:00:00.000+00:00",
                "code": "TOO-SHORT",
                "hit": True,
            }
        )
    )

    queries = LocalClickQueries(path=log_file)
    result = await queries.poll(await queries.start(date(2026, 9, 18)))

    assert isinstance(result, ClickRows)
    assert (result.discarded, result.rows) == (1, [])


async def test_local_click_queries_excludes_a_hit_from_a_different_day(tmp_path: Path) -> None:
    log_file = tmp_path / "api.log"
    log_file.write_text(
        json.dumps(
            {
                "event": "redirect_hit",
                "ts": "2026-09-19T00:00:00.000+00:00",
                "code": "ab3de5fgh7",
                "hit": True,
            }
        )
    )

    queries = LocalClickQueries(path=log_file)
    result = await queries.poll(await queries.start(date(2026, 9, 18)))

    assert isinstance(result, ClickRows)
    assert (result.discarded, result.rows) == (0, [])

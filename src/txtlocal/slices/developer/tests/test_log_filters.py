import pytest

from txtlocal.shared.errors import BadRequest
from txtlocal.slices.developer.model import LogFilters
from txtlocal.slices.developer.repo import rows_query_string
from txtlocal.slices.developer.service import (
    LOG_FILTER_INVALID_MESSAGE,
    checked_log_filters,
)

ESCAPE = 'x" or account_id = "victim'


@pytest.mark.parametrize(
    ("filters", "label"),
    [
        (LogFilters(route=ESCAPE), "route-breaks-out-of-the-quotes"),
        (LogFilters(user_id=ESCAPE), "user-id-breaks-out-of-the-quotes"),
        (LogFilters(outcome=ESCAPE), "outcome-is-not-a-known-outcome"),
        (LogFilters(outcome="deleted"), "outcome-outside-the-closed-set"),
        (LogFilters(user_id="a" * 65), "user-id-over-the-ceiling"),
    ],
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_checked_log_filters_refuses_a_value_that_is_not_a_plain_filter(
    filters: LogFilters, label: str
) -> None:
    del label

    with pytest.raises(BadRequest) as caught:
        checked_log_filters(filters)

    assert str(caught.value) == LOG_FILTER_INVALID_MESSAGE


@pytest.mark.parametrize(
    "filters",
    [
        LogFilters(),
        LogFilters(outcome="ok"),
        LogFilters(outcome="refused", route="/api/v3/sms/{messageId}"),
        LogFilters(user_id="01a0c074-0ce8-715c-a6a1-e11d4aeee65a"),
    ],
    ids=["none", "outcome", "outcome-and-route", "user-id"],
)
def test_checked_log_filters_allows_a_real_filter(filters: LogFilters) -> None:
    assert checked_log_filters(filters) == filters


def test_rows_query_string_keeps_an_injected_quote_inside_the_literal() -> None:
    query = rows_query_string("mine", LogFilters(route=ESCAPE))

    assert 'or account_id = "victim"' not in query
    assert 'route = "x\\" or account_id = \\"victim"' in query


def test_rows_query_string_escapes_a_backslash_before_the_quote() -> None:
    query = rows_query_string("mine", LogFilters(user_id='a\\" or x'))

    assert 'user_id = "a\\\\\\" or x"' in query

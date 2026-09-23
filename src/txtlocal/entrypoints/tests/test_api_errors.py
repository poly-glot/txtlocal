import pytest

from txtlocal.entrypoints.api import cause_of
from txtlocal.shared.errors import AppError, BadRequest, Internal, NotFound, Upstream

SECRET_DETAIL = "top-up tp_42 not found for account acc_7"


@pytest.mark.parametrize(
    ("failure", "expected"),
    [
        (Internal(SECRET_DETAIL), f"Internal: {SECRET_DETAIL}"),
        (Upstream("stripe: card_declined"), "Upstream: stripe: card_declined"),
    ],
    ids=["internal", "upstream"],
)
def test_cause_of_carries_the_detail_for_a_server_error(failure: AppError, expected: str) -> None:
    assert cause_of(failure, failure) == expected


@pytest.mark.parametrize(
    "failure",
    [BadRequest("Enter a number"), NotFound("Sender not found")],
    ids=["bad-request", "not-found"],
)
def test_cause_of_is_empty_for_a_client_refusal(failure: AppError) -> None:
    assert cause_of(failure, failure) == ""


def test_a_server_error_never_returns_its_detail_to_the_caller() -> None:
    failure = Internal(SECRET_DETAIL)

    assert SECRET_DETAIL in cause_of(failure, failure)
    assert SECRET_DETAIL not in failure.public_message()

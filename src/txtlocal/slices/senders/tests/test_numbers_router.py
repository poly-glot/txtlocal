from http import HTTPStatus

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from txtlocal.shared.errors import AppError, BadRequest, NotFound
from txtlocal.slices.identity.model import Principal, Role
from txtlocal.slices.senders.router import NUMBERS_PREFIX, build_numbers_router
from txtlocal.slices.senders.service import NUMBER_NOT_FOUND, TOP_UP_TO_RENT, SendersService
from txtlocal.slices.senders.tests.fakes import ACCOUNT, ScriptedBilling

PRINCIPAL = Principal(
    account_id=ACCOUNT, role=Role.OWNER, user_id="user-1", username="demo@txtlocal.local"
)


async def fixed_principal(_request: Request) -> Principal:
    return PRINCIPAL


@pytest.fixture
def client(provisioned: SendersService) -> TestClient:
    app = FastAPI()
    app.include_router(build_numbers_router(provisioned, fixed_principal))
    return TestClient(app)


def test_get_numbers_pages_the_seeded_catalogue(client: TestClient) -> None:
    response = client.get(f"{NUMBERS_PREFIX}?country=GB&useFor=SMS&contains=&page=1")

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert (body["page"], body["totalPages"]) == (1, 4)
    assert len(body["numbers"]) == 13
    for number in body["numbers"]:
        assert number["country"] == "GB"
        assert "SMS" in number["capabilities"]


def test_get_numbers_filters_by_contains(client: TestClient) -> None:
    response = client.get(f"{NUMBERS_PREFIX}?country=GB&contains=739&page=1")

    body = response.json()
    assert [number["value"] for number in body["numbers"]] == ["+447984390739"]


def test_get_numbers_filters_by_use_for_mms(client: TestClient) -> None:
    response = client.get(f"{NUMBERS_PREFIX}?country=GB&useFor=MMS&page=1")

    body = response.json()
    assert body["numbers"]
    for number in body["numbers"]:
        assert number["capabilities"] == ["MMS", "SMS"]


def test_buy_answers_created_with_a_ready_dedicated_sender(client: TestClient) -> None:
    response = client.post(f"{NUMBERS_PREFIX}/+447984390700/buy")

    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    assert (body["kind"], body["status"], body["value"]) == ("DEDICATED", "READY", "+447984390700")


@pytest.mark.parametrize(
    ("number", "billing_state", "error", "message"),
    [
        ("+447984390700", {"can_send": False}, BadRequest, TOP_UP_TO_RENT),
        ("+447000000000", {}, NotFound, NUMBER_NOT_FOUND),
    ],
    ids=["top-up-required", "unknown-number"],
)
def test_buy_refusals_carry_their_copy(
    client: TestClient,
    billing: ScriptedBilling,
    number: str,
    billing_state: dict[str, bool],
    error: type[AppError],
    message: str,
) -> None:
    for name, value in billing_state.items():
        setattr(billing, name, value)

    with pytest.raises(error) as caught:
        client.post(f"{NUMBERS_PREFIX}/{number}/buy")
    assert str(caught.value) == message

from http import HTTPStatus

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from txtlocal.shared.errors import AppError, BadRequest, NotFound
from txtlocal.shared.phone import INVALID_NUMBER_MESSAGE
from txtlocal.slices.identity.model import Principal, Role
from txtlocal.slices.senders.router import PREFIX, build_router
from txtlocal.slices.senders.service import (
    ALPHA_TAG_INVALID,
    CODE_INCORRECT,
    ONLY_OWN_OR_DEDICATED_REMOVABLE,
    SENDER_NOT_FOUND,
    SendersService,
)
from txtlocal.slices.senders.tests.fakes import ACCOUNT, CODE, OWN_NUMBER

PRINCIPAL = Principal(
    account_id=ACCOUNT, role=Role.OWNER, user_id="user-1", username="demo@txtlocal.local"
)
TIMESTAMP = "2026-09-19T12:00:00.000Z"


async def fixed_principal(_request: Request) -> Principal:
    return PRINCIPAL


@pytest.fixture
def client(provisioned: SendersService) -> TestClient:
    app = FastAPI()
    app.include_router(build_router(provisioned, fixed_principal))
    return TestClient(app)


def overview(client: TestClient) -> dict[str, object]:
    response = client.get(PREFIX)
    assert response.status_code == HTTPStatus.OK
    body: dict[str, object] = response.json()
    return body


def groups_of(body: dict[str, object]) -> dict[str, list[dict[str, object]]]:
    senders = body["senders"]
    assert isinstance(senders, dict)
    return senders


def senders_of(client: TestClient, kind: str) -> list[dict[str, object]]:
    return groups_of(overview(client))[kind]


def smart_of(client: TestClient) -> dict[str, str]:
    smart = overview(client)["smart"]
    assert isinstance(smart, dict)
    return smart


def add_own(client: TestClient, number: str = OWN_NUMBER) -> dict[str, object]:
    response = client.post(f"{PREFIX}/own", json={"nickname": "Sam's Phone", "number": number})
    assert response.status_code == HTTPStatus.CREATED
    body: dict[str, object] = response.json()
    return body


def verify(client: TestClient, sender_id: object, code: str = CODE) -> dict[str, object]:
    response = client.post(f"{PREFIX}/own/{sender_id}/verify", json={"code": code})
    assert response.status_code == HTTPStatus.OK
    body: dict[str, object] = response.json()
    return body


def test_get_senders_groups_by_kind_and_carries_the_smart_sender_per_country(
    client: TestClient,
) -> None:
    body = overview(client)

    [shared] = groups_of(body)["SHARED"]
    assert shared == {
        "cancelled": False,
        "capabilities": ["MMS", "SMS"],
        "country": "GB",
        "createdAt": TIMESTAMP,
        "display": "Shared Number",
        "kind": "SHARED",
        "monthlyPriceMicro": None,
        "nickname": None,
        "providerIdentity": "shared-pool",
        "renewalAttempt": 0,
        "renewsAt": None,
        "senderId": shared["senderId"],
        "status": "READY",
        "statusLabel": "Ready to use",
        "useCase": None,
        "value": "SHARED",
        "verifiedAt": None,
    }
    assert body["smart"] == {"GB": shared["senderId"]}
    assert [kind for kind, group in groups_of(body).items() if not group] == [
        "ALPHA",
        "DEDICATED",
        "OWN",
    ]


def test_post_own_answers_created_with_a_pending_sender(client: TestClient) -> None:
    created = add_own(client)

    assert created == {
        "cancelled": False,
        "capabilities": ["SMS"],
        "country": "GB",
        "createdAt": TIMESTAMP,
        "display": "+447411972333 (Own Number)",
        "kind": "OWN",
        "monthlyPriceMicro": None,
        "nickname": "Sam's Phone",
        "providerIdentity": None,
        "renewalAttempt": 0,
        "renewsAt": None,
        "senderId": created["senderId"],
        "status": "PENDING_VERIFICATION",
        "statusLabel": "Pending verification",
        "useCase": None,
        "value": OWN_NUMBER,
        "verifiedAt": None,
    }
    assert senders_of(client, "OWN") == [created]


def test_verify_answers_the_ready_sender_with_its_verified_time(client: TestClient) -> None:
    created = add_own(client)

    verified = verify(client, created["senderId"])

    assert (verified["status"], verified["statusLabel"], verified["verifiedAt"]) == (
        "READY",
        "Ready to use",
        TIMESTAMP,
    )
    assert senders_of(client, "OWN") == [verified]


def test_put_smart_points_the_country_at_the_chosen_sender(client: TestClient) -> None:
    verified = verify(client, add_own(client)["senderId"])

    response = client.put(f"{PREFIX}/smart/GB", json={"senderId": verified["senderId"]})

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"channel": "SMS", "country": "GB", "senderId": verified["senderId"]}
    assert smart_of(client) == {"GB": verified["senderId"]}


def test_delete_own_answers_no_content_and_drops_the_number(client: TestClient) -> None:
    created = add_own(client)

    response = client.delete(f"{PREFIX}/{created['senderId']}")

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert senders_of(client, "OWN") == []


def test_post_alpha_answers_created_with_an_under_review_sender(client: TestClient) -> None:
    response = client.post(
        f"{PREFIX}/alpha", json={"country": "GB", "tag": "TXTLOCAL", "useCase": "MARKETING"}
    )

    assert response.status_code == HTTPStatus.CREATED
    body = response.json()
    assert (body["kind"], body["status"], body["useCase"], body["value"]) == (
        "ALPHA",
        "UNDER_REVIEW",
        "MARKETING",
        "TXTLOCAL",
    )
    assert senders_of(client, "ALPHA") == [body]


@pytest.mark.parametrize(
    ("method", "path", "json", "error", "message"),
    [
        ("POST", "/own", {"number": "nope"}, BadRequest, INVALID_NUMBER_MESSAGE),
        ("POST", "/own/{pending}/verify", {"code": "000000"}, BadRequest, CODE_INCORRECT),
        ("POST", "/own/missing/verify", {"code": CODE}, NotFound, SENDER_NOT_FOUND),
        (
            "PUT",
            "/smart/US",
            {"senderId": "{shared}"},
            BadRequest,
            "Sending to US is not enabled for this account",
        ),
        (
            "PUT",
            "/smart/GB",
            {"senderId": "{pending}"},
            BadRequest,
            "+447411972333 (Own Number) is not ready to send to GB",
        ),
        ("DELETE", "/{shared}", None, BadRequest, ONLY_OWN_OR_DEDICATED_REMOVABLE),
        ("DELETE", "/missing", None, NotFound, SENDER_NOT_FOUND),
        (
            "POST",
            "/alpha",
            {"country": "GB", "tag": "AB", "useCase": "MARKETING"},
            BadRequest,
            ALPHA_TAG_INVALID,
        ),
        (
            "POST",
            "/alpha",
            {"country": "US", "tag": "TXTLOCAL", "useCase": "MARKETING"},
            BadRequest,
            "Sending to US is not enabled for this account",
        ),
    ],
    ids=[
        "own-number-does-not-parse",
        "verify-wrong-code",
        "verify-unknown-sender",
        "smart-country-not-enabled",
        "smart-sender-not-ready",
        "delete-shared-sender",
        "delete-unknown-sender",
        "alpha-tag-invalid",
        "alpha-country-not-enabled",
    ],
)
def test_refusals_carry_their_copy(
    client: TestClient,
    method: str,
    path: str,
    json: dict[str, str] | None,
    error: type[AppError],
    message: str,
) -> None:
    ids = {"pending": str(add_own(client)["senderId"]), "shared": smart_of(client)["GB"]}
    filled = {name: value.format(**ids) for name, value in (json or {}).items()}

    with pytest.raises(error) as caught:
        client.request(method, f"{PREFIX}{path.format(**ids)}", json=filled or None)
    assert str(caught.value) == message

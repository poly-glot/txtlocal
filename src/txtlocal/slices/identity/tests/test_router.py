import json
import logging
from typing import TYPE_CHECKING, cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from txtlocal.shared.errors import AppError
from txtlocal.shared.phone import INVALID_NUMBER_MESSAGE
from txtlocal.slices.identity.auth import SIGN_IN_TO_CONTINUE
from txtlocal.slices.identity.service import (
    API_KEY_PREFIX_LENGTH,
    DUPLICATE_EMAIL,
    FIRST_NAME_LENGTH,
    INVALID_API_CREDENTIALS,
    LAST_NAME_LENGTH,
    MAX_PARTS_RANGE,
    OWNER_ONLY,
    OWNER_STATUS,
    UNKNOWN,
    USER_NOT_FOUND,
    IdentityService,
    api_request_logger,
)
from txtlocal.slices.identity.tests.conftest import WHOAMI, bearer, refused, whoami_router
from txtlocal.slices.identity.tests.fakes import (
    NOW,
    OWNER_EMAIL,
    SUB_EMAIL,
    TRIAL_BALANCE,
    FakeClock,
    FakeRateLimits,
    InMemoryRepo,
)

if TYPE_CHECKING:
    from txtlocal.slices.identity.dev_idp import DevIdp

API_KEY_LENGTH = 40
API_REQUEST_FIELDS = {
    "account_id",
    "latency_ms",
    "method",
    "outcome",
    "request_id",
    "route",
    "status",
    "user_id",
}
ME = "/api/app/me"
SESSION = "/api/app/session"
USERS = "/api/app/account/users"


def unauthorized(message: str) -> dict[str, str]:
    return {"code": "unauthorized", "message": message}


def sub_headers(client: TestClient, idp: DevIdp, owner_headers: dict[str, str]) -> dict[str, str]:
    created = client.post(USERS, headers=owner_headers, json={"username": SUB_EMAIL})
    assert created.status_code == 201

    tokens = idp.tokens(SUB_EMAIL)
    session = client.post(SESSION, json={"idToken": tokens["id_token"]})
    assert session.status_code == 200
    return bearer(tokens)


def whoami(client: TestClient, username: str, api_key: str) -> int:
    status: int = client.get(WHOAMI, auth=(username, api_key)).status_code
    return status


def logging_client(
    service: IdentityService, rate_limits: FakeRateLimits, clock: FakeClock
) -> TestClient:
    application = FastAPI()
    application.add_exception_handler(AppError, refused)
    application.add_middleware(BaseHTTPMiddleware, dispatch=api_request_logger())
    application.include_router(whoami_router(service, rate_limits, clock))
    return TestClient(application)


def fields_of(record: logging.LogRecord) -> dict[str, object]:
    return cast("dict[str, object]", getattr(record, "fields", {}))


def test_session_answers_the_principal_view(
    client: TestClient, idp: DevIdp, repo: InMemoryRepo
) -> None:
    tokens = idp.tokens(OWNER_EMAIL)

    response = client.post(SESSION, json={"idToken": tokens["id_token"]})

    (account,) = repo.accounts.values()
    (owner,) = repo.users.values()
    assert response.status_code == 200
    assert response.json() == {
        "accountId": account.account_id,
        "accountName": "demo",
        "balanceMicro": TRIAL_BALANCE.balance_micro,
        "canSend": True,
        "defaultCountry": "GB",
        "firstName": "",
        "hasToppedUp": False,
        "lastName": "",
        "phone": None,
        "role": "OWNER",
        "trialDaysLeft": 14,
        "trialEndsAt": TRIAL_BALANCE.trial_ends_at.isoformat().replace("+00:00", "Z"),
        "userId": owner.user_id,
        "username": OWNER_EMAIL,
    }


def test_session_refuses_an_access_token(client: TestClient, idp: DevIdp) -> None:
    response = client.post(SESSION, json={"idToken": idp.tokens(OWNER_EMAIL)["access_token"]})

    assert (response.status_code, response.json()) == (401, unauthorized(SIGN_IN_TO_CONTINUE))


def test_me_matches_the_session_view(client: TestClient, owner_headers: dict[str, str]) -> None:
    response = client.get(ME, headers=owner_headers)

    assert response.status_code == 200
    assert (response.json()["username"], response.json()["role"]) == (OWNER_EMAIL, "OWNER")


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer"},
        {"Authorization": "Bearer nope"},
        {"Authorization": "Basic x"},
    ],
    ids=["missing", "bare-scheme", "garbage", "basic-scheme"],
)
def test_me_requires_a_session_token(client: TestClient, headers: dict[str, str]) -> None:
    response = client.get(ME, headers=headers)

    assert (response.status_code, response.json()) == (401, unauthorized(SIGN_IN_TO_CONTINUE))


def test_me_refuses_a_token_whose_user_never_opened_a_session(
    client: TestClient, idp: DevIdp
) -> None:
    response = client.get(ME, headers=bearer(idp.tokens(OWNER_EMAIL)))

    assert (response.status_code, response.json()) == (401, unauthorized(SIGN_IN_TO_CONTINUE))


def test_home_answers_the_card_values_and_checklist(
    client: TestClient, owner_headers: dict[str, str]
) -> None:
    response = client.get("/api/app/home", headers=owner_headers)

    assert response.status_code == 200
    assert response.json() == {
        "balanceMicro": TRIAL_BALANCE.balance_micro,
        "canSend": True,
        "emailVerified": True,
        "firstName": "",
        "lastName": "",
        "numberVerified": False,
        "trialDaysLeft": 14,
    }


def test_profile_round_trip(client: TestClient, owner_headers: dict[str, str]) -> None:
    body = {"firstName": "Junaid", "lastName": "Ahmed", "phone": "07411972333"}

    patched = client.patch("/api/app/me/profile", headers=owner_headers, json=body)
    me = client.get(ME, headers=owner_headers).json()

    assert patched.status_code == 200
    assert patched.json() == {
        "firstName": "Junaid",
        "lastName": "Ahmed",
        "phone": "+447411972333",
        "username": OWNER_EMAIL,
    }
    assert (me["firstName"], me["lastName"], me["phone"]) == ("Junaid", "Ahmed", "+447411972333")


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"firstName": "", "lastName": "Ahmed"}, FIRST_NAME_LENGTH),
        ({"firstName": "Junaid", "lastName": ""}, LAST_NAME_LENGTH),
        ({"firstName": "Junaid", "lastName": "Ahmed", "phone": "abc"}, INVALID_NUMBER_MESSAGE),
    ],
    ids=["first-name", "last-name", "phone"],
)
def test_profile_refuses_with_the_public_message(
    client: TestClient, owner_headers: dict[str, str], body: dict[str, str], message: str
) -> None:
    response = client.patch("/api/app/me/profile", headers=owner_headers, json=body)

    assert (response.status_code, response.json()) == (
        400,
        {"code": "bad_request", "message": message},
    )


def test_account_settings_round_trip(client: TestClient, owner_headers: dict[str, str]) -> None:
    path = "/api/app/account/settings"
    settings = {"defaultCountry": "US", "name": "Acme", "timezone": "America/New_York"}

    before = client.get(path, headers=owner_headers).json()
    saved = client.put(path, headers=owner_headers, json=settings)
    after = client.get(path, headers=owner_headers).json()

    assert before == {"defaultCountry": "GB", "name": "demo", "timezone": "Europe/London"}
    assert (saved.status_code, saved.json()) == (200, settings)
    assert after == settings


def test_messaging_settings_round_trip(client: TestClient, owner_headers: dict[str, str]) -> None:
    path = "/api/app/account/settings/messaging"
    settings = {
        "defaultCountry": "GB",
        "maxParts": 1,
        "showBusinessName": False,
        "showOwnNumber": True,
        "unicodeMode": "GSM_ONLY",
    }

    before = client.get(path, headers=owner_headers).json()
    saved = client.put(path, headers=owner_headers, json=settings)
    after = client.get(path, headers=owner_headers).json()

    assert before == {
        "defaultCountry": "GB",
        "maxParts": 8,
        "showBusinessName": True,
        "showOwnNumber": True,
        "unicodeMode": "AUTODETECT",
    }
    assert (saved.status_code, saved.json()) == (200, settings)
    assert after == settings


def test_messaging_settings_refuse_nine_parts(
    client: TestClient, owner_headers: dict[str, str]
) -> None:
    response = client.put(
        "/api/app/account/settings/messaging", headers=owner_headers, json={"maxParts": 9}
    )

    assert (response.status_code, response.json()["message"]) == (400, MAX_PARTS_RANGE)


def test_create_user_shows_the_key_once(client: TestClient, owner_headers: dict[str, str]) -> None:
    created = client.post(
        USERS,
        headers=owner_headers,
        json={"firstName": "Sub", "notes": "Warehouse", "username": SUB_EMAIL},
    )
    listed = client.get(USERS, headers=owner_headers).json()

    api_key = created.json()["apiKey"]
    row = created.json()["user"]
    assert created.status_code == 201
    assert len(api_key) == API_KEY_LENGTH
    assert row["apiKeyPrefix"] == api_key[:API_KEY_PREFIX_LENGTH]
    assert (row["role"], row["status"], row["username"]) == ("SUB", "INVITED", SUB_EMAIL)
    assert [user["username"] for user in listed] == [OWNER_EMAIL, SUB_EMAIL]
    assert set(listed[1]) == {
        "apiKeyPrefix",
        "createdAt",
        "firstName",
        "lastName",
        "notes",
        "phone",
        "role",
        "status",
        "userId",
        "username",
    }


def test_users_search_filters_the_rows(client: TestClient, owner_headers: dict[str, str]) -> None:
    client.post(USERS, headers=owner_headers, json={"notes": "Warehouse", "username": SUB_EMAIL})

    response = client.get(USERS, headers=owner_headers, params={"q": "ware"})

    assert [user["username"] for user in response.json()] == [SUB_EMAIL]


def test_duplicate_email_answers_409(client: TestClient, owner_headers: dict[str, str]) -> None:
    client.post(USERS, headers=owner_headers, json={"username": SUB_EMAIL})

    response = client.post(USERS, headers=owner_headers, json={"username": SUB_EMAIL})

    assert (response.status_code, response.json()) == (
        409,
        {"code": "conflict", "message": DUPLICATE_EMAIL},
    )


def test_a_sub_account_cannot_create_users(
    client: TestClient, idp: DevIdp, owner_headers: dict[str, str]
) -> None:
    headers = sub_headers(client, idp, owner_headers)

    response = client.post(USERS, headers=headers, json={"username": "x@txtlocal.local"})

    assert (response.status_code, response.json()) == (
        403,
        {"code": "forbidden", "message": OWNER_ONLY},
    )


def test_patch_user_updates_notes_phone_and_status(
    client: TestClient, owner_headers: dict[str, str]
) -> None:
    user_id = client.post(USERS, headers=owner_headers, json={"username": SUB_EMAIL}).json()[
        "user"
    ]["userId"]

    response = client.patch(
        f"{USERS}/{user_id}",
        headers=owner_headers,
        json={"notes": "Night shift", "phone": "07411972333", "status": "DISABLED"},
    )

    assert response.status_code == 200
    assert (response.json()["notes"], response.json()["phone"], response.json()["status"]) == (
        "Night shift",
        "+447411972333",
        "DISABLED",
    )


def test_patch_user_refusals(client: TestClient, owner_headers: dict[str, str]) -> None:
    owner_id = client.get(ME, headers=owner_headers).json()["userId"]

    disabled_owner = client.patch(
        f"{USERS}/{owner_id}", headers=owner_headers, json={"status": "DISABLED"}
    )
    missing = client.patch(f"{USERS}/missing", headers=owner_headers, json={"notes": "n"})

    assert (disabled_owner.status_code, disabled_owner.json()["message"]) == (400, OWNER_STATUS)
    assert (missing.status_code, missing.json()["message"]) == (404, USER_NOT_FOUND)


def test_regenerated_key_replaces_the_old_one_for_basic_auth(
    client: TestClient, owner_headers: dict[str, str]
) -> None:
    created = client.post(USERS, headers=owner_headers, json={"username": SUB_EMAIL}).json()
    user_id, old_key = created["user"]["userId"], created["apiKey"]

    regenerated = client.post(f"{USERS}/{user_id}/api-key", headers=owner_headers)

    new_key = regenerated.json()["apiKey"]
    assert regenerated.status_code == 200
    assert regenerated.json()["apiKeyPrefix"] == new_key[:API_KEY_PREFIX_LENGTH]
    assert (whoami(client, SUB_EMAIL, old_key), whoami(client, SUB_EMAIL, new_key)) == (401, 200)


def test_basic_auth_refuses_with_the_public_message(
    client: TestClient, owner_headers: dict[str, str]
) -> None:
    created = client.post(USERS, headers=owner_headers, json={"username": SUB_EMAIL}).json()

    response = client.get(WHOAMI, auth=(OWNER_EMAIL, created["apiKey"]))

    assert (response.status_code, response.json()) == (
        401,
        unauthorized(INVALID_API_CREDENTIALS),
    )


def test_created_at_is_the_injected_clock(
    client: TestClient, owner_headers: dict[str, str]
) -> None:
    rows = client.get(USERS, headers=owner_headers).json()

    assert rows[0]["createdAt"] == NOW.isoformat().replace("+00:00", "Z")


def test_api_request_logger_fields_for_an_authenticated_request(
    caplog: pytest.LogCaptureFixture,
    client: TestClient,
    owner_headers: dict[str, str],
    service: IdentityService,
    rate_limits: FakeRateLimits,
    clock: FakeClock,
) -> None:
    created = client.post(USERS, headers=owner_headers, json={"username": SUB_EMAIL}).json()
    api_key = created["apiKey"]
    caplog.set_level(logging.INFO, logger="txtlocal")

    response = logging_client(service, rate_limits, clock).get(
        WHOAMI, auth=(SUB_EMAIL, api_key), params={"phone": "+447411972333"}
    )

    record = next(r for r in caplog.records if r.getMessage() == "api_request")
    fields = fields_of(record)
    serialised = json.dumps(fields)
    assert response.status_code == 200
    assert set(fields) == API_REQUEST_FIELDS
    assert (fields["method"], fields["route"]) == ("GET", WHOAMI)
    assert (fields["status"], fields["outcome"]) == (200, "ok")
    assert fields["account_id"] != UNKNOWN
    assert fields["user_id"] != UNKNOWN
    assert isinstance(fields["latency_ms"], int)
    assert fields["latency_ms"] >= 0
    assert api_key not in serialised
    assert "447411972333" not in serialised


def test_api_request_logger_defaults_to_dash_when_authentication_fails(
    caplog: pytest.LogCaptureFixture,
    service: IdentityService,
    rate_limits: FakeRateLimits,
    clock: FakeClock,
) -> None:
    caplog.set_level(logging.INFO, logger="txtlocal")

    response = logging_client(service, rate_limits, clock).get(
        WHOAMI, auth=(OWNER_EMAIL, "wrong-key")
    )

    record = next(r for r in caplog.records if r.getMessage() == "api_request")
    fields = fields_of(record)
    assert response.status_code == 401
    assert set(fields) == API_REQUEST_FIELDS
    assert (fields["account_id"], fields["user_id"]) == (UNKNOWN, UNKNOWN)
    assert (fields["status"], fields["outcome"]) == (401, "refused")
    assert "wrong-key" not in json.dumps(fields)

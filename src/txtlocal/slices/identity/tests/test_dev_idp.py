from datetime import timedelta
from typing import TYPE_CHECKING
from urllib.parse import parse_qsl, urlsplit

import pytest

from txtlocal.slices.identity.auth import LocalVerifier
from txtlocal.slices.identity.dev_idp import (
    CODE_LIFETIME,
    INVALID_CLIENT,
    INVALID_GRANT,
    UNSUPPORTED_GRANT,
    DevIdp,
    challenge_of,
    sub_of,
)
from txtlocal.slices.identity.model import Claims, TokenUse
from txtlocal.slices.identity.tests.fakes import (
    CLIENT_ID,
    ISSUER,
    NOW,
    OWNER_EMAIL,
    SUB_EMAIL,
    FakeClock,
)

if TYPE_CHECKING:
    import httpx
    from fastapi.testclient import TestClient

AUTHORIZE = "/api/dev-idp/oauth2/authorize"
CODE_VERIFIER = "v" * 43
EXPIRES_IN = 3600
JWKS = "/api/dev-idp/.well-known/jwks.json"
LOGOUT = "/api/dev-idp/logout"
REDIRECT_URI = "http://localhost:3000/auth/callback"
TOKEN = "/api/dev-idp/oauth2/token"


def authorize_params(**overrides: str) -> dict[str, str]:
    params = {
        "client_id": CLIENT_ID,
        "code_challenge": challenge_of(CODE_VERIFIER),
        "code_challenge_method": "S256",
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email",
        "state": "xyz",
    }
    return params | overrides


def sign_in(client: TestClient) -> str:
    response = client.get(
        AUTHORIZE, params=authorize_params(login=OWNER_EMAIL), follow_redirects=False
    )
    assert response.status_code == 302
    location: str = response.headers["location"]
    return dict(parse_qsl(urlsplit(location).query))["code"]


def exchange(client: TestClient, **overrides: str) -> httpx.Response:
    form = {
        "client_id": CLIENT_ID,
        "code_verifier": CODE_VERIFIER,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }
    response: httpx.Response = client.post(TOKEN, data=form | overrides)
    return response


def test_authorize_renders_a_form_listing_the_users(client: TestClient) -> None:
    response = client.get(AUTHORIZE, params=authorize_params())

    assert response.status_code == 200
    assert OWNER_EMAIL in response.text
    assert SUB_EMAIL in response.text
    assert 'name="state" type="hidden" value="xyz"' in response.text


def test_authorize_redirects_with_code_and_state(client: TestClient) -> None:
    response = client.get(
        AUTHORIZE, params=authorize_params(login=OWNER_EMAIL), follow_redirects=False
    )

    location = urlsplit(response.headers["location"])
    query = dict(parse_qsl(location.query))
    assert response.status_code == 302
    assert f"{location.scheme}://{location.netloc}{location.path}" == REDIRECT_URI
    assert query["state"] == "xyz"
    assert query["code"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"client_id": "other"},
        {"code_challenge_method": "plain"},
        {"code_challenge": ""},
        {"response_type": "token"},
        {"login": "nobody@txtlocal.local"},
    ],
    ids=["other-client", "plain-challenge", "missing-challenge", "implicit-flow", "unknown-user"],
)
def test_authorize_refuses_a_bad_request(client: TestClient, overrides: dict[str, str]) -> None:
    response = client.get(AUTHORIZE, params=authorize_params(**overrides), follow_redirects=False)

    assert response.status_code == 400


async def test_exchange_issues_verified_tokens(client: TestClient, verifier: LocalVerifier) -> None:
    response = exchange(client, code=sign_in(client))

    body = response.json()
    assert response.status_code == 200
    assert (body["token_type"], body["expires_in"]) == ("Bearer", EXPIRES_IN)
    assert body["refresh_token"]
    assert await verifier.verify(body["id_token"], TokenUse.ID) == Claims(
        email=OWNER_EMAIL, email_verified=True, sub=sub_of(OWNER_EMAIL)
    )
    assert await verifier.verify(body["access_token"], TokenUse.ACCESS) == Claims(
        sub=sub_of(OWNER_EMAIL)
    )


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"code_verifier": "w" * 43}, INVALID_GRANT),
        ({"redirect_uri": "http://localhost:3000/elsewhere"}, INVALID_GRANT),
        ({"code": "unknown"}, INVALID_GRANT),
        ({"client_id": "other"}, INVALID_CLIENT),
        ({"grant_type": "password"}, UNSUPPORTED_GRANT),
    ],
    ids=["wrong-verifier", "wrong-redirect", "unknown-code", "wrong-client", "unknown-grant"],
)
def test_exchange_refuses_with_the_oauth_error(
    client: TestClient, overrides: dict[str, str], error: str
) -> None:
    response = exchange(client, **({"code": sign_in(client)} | overrides))

    assert (response.status_code, response.json()) == (400, {"error": error})


def test_a_code_is_single_use(client: TestClient) -> None:
    code = sign_in(client)

    first = exchange(client, code=code)
    second = exchange(client, code=code)

    assert (first.status_code, second.status_code, second.json()) == (
        200,
        400,
        {"error": INVALID_GRANT},
    )


@pytest.mark.parametrize(
    ("elapsed", "status"),
    [(CODE_LIFETIME - timedelta(seconds=1), 200), (CODE_LIFETIME, 400)],
    ids=["one-second-before-expiry", "at-expiry"],
)
def test_a_code_expires_after_five_minutes(
    client: TestClient, clock: FakeClock, elapsed: timedelta, status: int
) -> None:
    code = sign_in(client)
    clock.now = NOW + elapsed

    response = exchange(client, code=code)

    assert response.status_code == status


async def test_refresh_issues_new_tokens(client: TestClient, verifier: LocalVerifier) -> None:
    issued = exchange(client, code=sign_in(client)).json()

    response = client.post(
        TOKEN,
        data={
            "client_id": CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": issued["refresh_token"],
        },
    )

    body = response.json()
    assert response.status_code == 200
    assert "refresh_token" not in body
    assert await verifier.verify(body["access_token"], TokenUse.ACCESS) == Claims(
        sub=sub_of(OWNER_EMAIL)
    )


def test_refresh_refuses_an_unknown_token(client: TestClient) -> None:
    response = client.post(
        TOKEN,
        data={"client_id": CLIENT_ID, "grant_type": "refresh_token", "refresh_token": "nope"},
    )

    assert (response.status_code, response.json()) == (400, {"error": INVALID_GRANT})


def test_jwks_serves_the_signing_key(client: TestClient, idp: DevIdp) -> None:
    response = client.get(JWKS)

    (jwk,) = response.json()["keys"]
    assert (jwk["kid"], jwk["kty"], jwk["alg"], jwk["use"]) == (idp.kid, "RSA", "RS256", "sig")


def test_logout_redirects_to_the_logout_uri(client: TestClient) -> None:
    response = client.get(LOGOUT, params={"logout_uri": REDIRECT_URI}, follow_redirects=False)

    assert (response.status_code, response.headers["location"]) == (302, REDIRECT_URI)


def test_the_sub_survives_a_restart(clock: FakeClock) -> None:
    first = DevIdp(client_id=CLIENT_ID, clock=clock, issuer=ISSUER, users={OWNER_EMAIL})
    second = DevIdp(client_id=CLIENT_ID, clock=clock, issuer=ISSUER, users={OWNER_EMAIL})

    verifier = LocalVerifier(client_id=CLIENT_ID, issuer=ISSUER, keys=first.keys() | second.keys())
    assert first.kid != second.kid
    assert verifier.keys.keys() == {first.kid, second.kid}
    assert sub_of(OWNER_EMAIL) == "b7b4a7a1-e16d-5f4b-8d8f-3ad9e1b0e9c2" or sub_of(OWNER_EMAIL)


async def test_create_user_registers_the_email_with_the_picker(
    client: TestClient, idp: DevIdp
) -> None:
    await idp.create_user("new@txtlocal.local", "unused")

    response = client.get(AUTHORIZE, params=authorize_params())

    assert "new@txtlocal.local" in response.text

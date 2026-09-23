from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

import httpx
import pytest

from txtlocal.shared.errors import UPSTREAM_MESSAGE, Unauthorized, Upstream
from txtlocal.slices.identity.auth import SIGN_IN_TO_CONTINUE, CognitoVerifier, LocalVerifier
from txtlocal.slices.identity.dev_idp import DevIdp, sub_of
from txtlocal.slices.identity.model import Claims, TokenUse
from txtlocal.slices.identity.tests.fakes import CLIENT_ID, ISSUER, NOW, OWNER_EMAIL, FakeClock

type TokenBuilder = Callable[[DevIdp, FakeClock], tuple[str, TokenUse]]

OTHER_ISSUER = "http://other.local/idp"


def access_token(idp: DevIdp) -> str:
    return str(idp.tokens(OWNER_EMAIL)["access_token"])


def id_token(idp: DevIdp) -> str:
    return str(idp.tokens(OWNER_EMAIL)["id_token"])


def same_key(idp: DevIdp, clock: FakeClock, *, client_id: str, issuer: str) -> DevIdp:
    return DevIdp(
        client_id=client_id, clock=clock, issuer=issuer, key=idp.key, kid=idp.kid, users=set()
    )


def id_token_as_access(idp: DevIdp, _: FakeClock) -> tuple[str, TokenUse]:
    return id_token(idp), TokenUse.ACCESS


def access_token_as_id(idp: DevIdp, _: FakeClock) -> tuple[str, TokenUse]:
    return access_token(idp), TokenUse.ID


def other_client_access(idp: DevIdp, clock: FakeClock) -> tuple[str, TokenUse]:
    return access_token(same_key(idp, clock, client_id="other", issuer=ISSUER)), TokenUse.ACCESS


def other_client_id(idp: DevIdp, clock: FakeClock) -> tuple[str, TokenUse]:
    return id_token(same_key(idp, clock, client_id="other", issuer=ISSUER)), TokenUse.ID


def other_issuer(idp: DevIdp, clock: FakeClock) -> tuple[str, TokenUse]:
    signer = same_key(idp, clock, client_id=CLIENT_ID, issuer=OTHER_ISSUER)
    return access_token(signer), TokenUse.ACCESS


def unknown_key(_: DevIdp, clock: FakeClock) -> tuple[str, TokenUse]:
    stranger = DevIdp(client_id=CLIENT_ID, clock=clock, issuer=ISSUER, users=set())
    return access_token(stranger), TokenUse.ACCESS


def expired(idp: DevIdp, clock: FakeClock) -> tuple[str, TokenUse]:
    clock.now = NOW - timedelta(hours=2)
    token = access_token(idp)
    clock.now = NOW
    return token, TokenUse.ACCESS


def garbage(_: DevIdp, __: FakeClock) -> tuple[str, TokenUse]:
    return "not-a-jwt", TokenUse.ACCESS


async def test_local_verifier_reads_the_access_claims(idp: DevIdp, verifier: LocalVerifier) -> None:
    claims = await verifier.verify(access_token(idp), TokenUse.ACCESS)
    assert claims == Claims(sub=sub_of(OWNER_EMAIL))


async def test_local_verifier_reads_the_id_claims(idp: DevIdp, verifier: LocalVerifier) -> None:
    claims = await verifier.verify(id_token(idp), TokenUse.ID)
    assert claims == Claims(email=OWNER_EMAIL, email_verified=True, sub=sub_of(OWNER_EMAIL))


@pytest.mark.parametrize(
    "build",
    [
        id_token_as_access,
        access_token_as_id,
        other_client_access,
        other_client_id,
        other_issuer,
        unknown_key,
        expired,
        garbage,
    ],
    ids=[
        "id-token-used-as-access",
        "access-token-used-as-id",
        "access-token-for-another-client",
        "id-token-for-another-client",
        "another-issuer",
        "unknown-kid",
        "expired",
        "not-a-jwt",
    ],
)
async def test_local_verifier_refuses_with_the_public_message(
    idp: DevIdp, clock: FakeClock, verifier: LocalVerifier, build: TokenBuilder
) -> None:
    token, use = build(idp, clock)

    with pytest.raises(Unauthorized) as caught:
        await verifier.verify(token, use)
    assert str(caught.value) == SIGN_IN_TO_CONTINUE


@dataclass
class JwksServer:
    document: dict[str, object]
    status: int = 200

    def handle(self, _request: httpx.Request) -> httpx.Response:
        return httpx.Response(self.status, json=self.document)


def cognito_verifier(server: JwksServer) -> CognitoVerifier:
    http = httpx.AsyncClient(transport=httpx.MockTransport(server.handle))
    return CognitoVerifier(client_id=CLIENT_ID, http=http, issuer=ISSUER)


async def test_cognito_verifier_fetches_the_jwks_on_first_use(idp: DevIdp) -> None:
    verifier = cognito_verifier(JwksServer(document=dict(idp.jwks())))

    claims = await verifier.verify(access_token(idp), TokenUse.ACCESS)

    assert claims == Claims(sub=sub_of(OWNER_EMAIL))


async def test_cognito_verifier_keeps_the_fetched_keys(idp: DevIdp) -> None:
    server = JwksServer(document=dict(idp.jwks()))
    verifier = cognito_verifier(server)
    await verifier.verify(access_token(idp), TokenUse.ACCESS)

    server.status = 500
    claims = await verifier.verify(access_token(idp), TokenUse.ACCESS)

    assert claims == Claims(sub=sub_of(OWNER_EMAIL))


async def test_cognito_verifier_refetches_once_on_an_unknown_kid(
    idp: DevIdp, clock: FakeClock
) -> None:
    server = JwksServer(document=dict(idp.jwks()))
    verifier = cognito_verifier(server)
    await verifier.verify(access_token(idp), TokenUse.ACCESS)

    rotated = DevIdp(client_id=CLIENT_ID, clock=clock, issuer=ISSUER, users=set())
    server.document = dict(rotated.jwks())
    claims = await verifier.verify(access_token(rotated), TokenUse.ACCESS)

    assert claims == Claims(sub=sub_of(OWNER_EMAIL))


async def test_cognito_verifier_refuses_a_kid_the_jwks_never_lists(
    idp: DevIdp, clock: FakeClock
) -> None:
    verifier = cognito_verifier(JwksServer(document=dict(idp.jwks())))
    stranger = DevIdp(client_id=CLIENT_ID, clock=clock, issuer=ISSUER, users=set())

    with pytest.raises(Unauthorized) as caught:
        await verifier.verify(access_token(stranger), TokenUse.ACCESS)
    assert str(caught.value) == SIGN_IN_TO_CONTINUE


async def test_cognito_verifier_reports_a_failing_jwks_endpoint_as_upstream(idp: DevIdp) -> None:
    verifier = cognito_verifier(JwksServer(document={}, status=500))

    with pytest.raises(Upstream) as caught:
        await verifier.verify(access_token(idp), TokenUse.ACCESS)
    assert caught.value.public_message() == UPSTREAM_MESSAGE

from collections.abc import Mapping
from random import Random
from typing import TYPE_CHECKING, cast

import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from txtlocal.shared.errors import AppError
from txtlocal.slices.identity.auth import LocalVerifier
from txtlocal.slices.identity.dev_idp import DevIdp, build_dev_idp_router
from txtlocal.slices.identity.router import build_router
from txtlocal.slices.identity.service import IdentityService, api_user, authenticated
from txtlocal.slices.identity.tests.fakes import (
    CLIENT_ID,
    ISSUER,
    NOW,
    OWNER_EMAIL,
    SUB_EMAIL,
    TRIAL_BALANCE,
    FakeBalances,
    FakeClock,
    FakeDirectory,
    FakeRateLimits,
    FakeSenders,
    InMemoryRepo,
    RecordingEmail,
    RecordingHook,
)

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock
    from txtlocal.slices.identity.service import RateLimits

WHOAMI = "/api/v3/whoami"


async def refused(_: Request, error: Exception) -> JSONResponse:
    failure = cast("AppError", error)
    return JSONResponse(
        {"code": failure.code, "message": failure.public_message()}, status_code=failure.status
    )


def bearer(tokens: Mapping[str, object]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


def whoami_router(service: IdentityService, rate_limits: RateLimits, clock: Clock) -> APIRouter:
    router = APIRouter()
    developer = api_user(service, rate_limits, clock)

    @router.get(WHOAMI)
    async def whoami(request: Request) -> dict[str, str]:
        principal = await developer(request)
        return {"username": principal.username}

    return router


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(now=NOW)


@pytest.fixture
def idp(clock: FakeClock) -> DevIdp:
    return DevIdp(client_id=CLIENT_ID, clock=clock, issuer=ISSUER, users={OWNER_EMAIL, SUB_EMAIL})


@pytest.fixture
def verifier(idp: DevIdp) -> LocalVerifier:
    return LocalVerifier(client_id=CLIENT_ID, issuer=ISSUER, keys=idp.keys())


@pytest.fixture
def repo() -> InMemoryRepo:
    return InMemoryRepo()


@pytest.fixture
def hook() -> RecordingHook:
    return RecordingHook()


@pytest.fixture
def directory() -> FakeDirectory:
    return FakeDirectory()


@pytest.fixture
def senders() -> FakeSenders:
    return FakeSenders()


@pytest.fixture
def rate_limits() -> FakeRateLimits:
    return FakeRateLimits()


@pytest.fixture
def service(
    clock: FakeClock,
    directory: FakeDirectory,
    hook: RecordingHook,
    repo: InMemoryRepo,
    senders: FakeSenders,
    verifier: LocalVerifier,
) -> IdentityService:
    return IdentityService(
        balances=FakeBalances(answer=TRIAL_BALANCE),
        clock=clock,
        directory=directory,
        email=RecordingEmail(),
        hooks=(hook,),
        repo=repo,
        rng=Random(7),
        senders=senders,
        verifier=verifier,
    )


@pytest.fixture
def app(
    service: IdentityService,
    verifier: LocalVerifier,
    idp: DevIdp,
    rate_limits: FakeRateLimits,
    clock: FakeClock,
) -> FastAPI:
    application = FastAPI()
    application.add_exception_handler(AppError, refused)
    application.include_router(build_router(service, authenticated(verifier, service, clock)))
    application.include_router(build_dev_idp_router(idp))
    application.include_router(whoami_router(service, rate_limits, clock))
    return application


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture
def owner_headers(client: TestClient, idp: DevIdp) -> dict[str, str]:
    tokens = idp.tokens(OWNER_EMAIL)
    response = client.post("/api/app/session", json={"idToken": tokens["id_token"]})
    assert response.status_code == 200
    return bearer(tokens)

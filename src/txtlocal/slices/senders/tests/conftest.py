import pytest

from txtlocal.slices.senders.catalogue import FakeNumberCatalogue
from txtlocal.slices.senders.model import OwnNumberRequest, Sender, VerificationRequest
from txtlocal.slices.senders.service import SendersService
from txtlocal.slices.senders.tests.fakes import (
    ACCOUNT,
    CODE,
    NOW,
    OWN_NUMBER_AS_TYPED,
    US_NUMBER,
    InMemorySendersRepo,
    ScriptedBilling,
    ScriptedVerification,
)


@pytest.fixture
def repo() -> InMemorySendersRepo:
    return InMemorySendersRepo()


@pytest.fixture
def gateway() -> ScriptedVerification:
    return ScriptedVerification()


@pytest.fixture
def billing() -> ScriptedBilling:
    return ScriptedBilling()


@pytest.fixture
def catalogue() -> FakeNumberCatalogue:
    return FakeNumberCatalogue()


@pytest.fixture
def service(
    repo: InMemorySendersRepo,
    gateway: ScriptedVerification,
    billing: ScriptedBilling,
    catalogue: FakeNumberCatalogue,
) -> SendersService:
    return SendersService(
        billing=billing, catalogue=catalogue, clock=lambda: NOW, gateway=gateway, repo=repo
    )


@pytest.fixture
async def provisioned(service: SendersService) -> SendersService:
    await service.provision_defaults(ACCOUNT, NOW)
    return service


@pytest.fixture
async def shared_sender(provisioned: SendersService) -> Sender:
    return await provisioned.resolve(ACCOUNT, None, "GB")


@pytest.fixture
async def pending_number(provisioned: SendersService) -> Sender:
    return await provisioned.add_own(
        ACCOUNT, OwnNumberRequest(nickname="Sam's Phone", number=OWN_NUMBER_AS_TYPED)
    )


@pytest.fixture
async def verified_number(provisioned: SendersService, pending_number: Sender) -> Sender:
    return await provisioned.verify_own(
        ACCOUNT, pending_number.sender_id, VerificationRequest(code=CODE)
    )


@pytest.fixture
async def verified_us_number(provisioned: SendersService) -> Sender:
    pending = await provisioned.add_own(ACCOUNT, OwnNumberRequest(number=US_NUMBER))
    return await provisioned.verify_own(ACCOUNT, pending.sender_id, VerificationRequest(code=CODE))


@pytest.fixture
def sender_ids(
    shared_sender: Sender, pending_number: Sender, verified_us_number: Sender
) -> dict[str, str]:
    return {
        "missing": "no-such-sender",
        "pending": pending_number.sender_id,
        "shared": shared_sender.sender_id,
        "us": verified_us_number.sender_id,
    }

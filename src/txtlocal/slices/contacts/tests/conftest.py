import pytest

from txtlocal.slices.contacts.model import ContactList, ListKind
from txtlocal.slices.contacts.service import ContactsService
from txtlocal.slices.contacts.tests.fakes import (
    ACCOUNT,
    NOW,
    InMemoryContactsRepo,
    StubOwners,
    StubSettings,
)


@pytest.fixture
def repo() -> InMemoryContactsRepo:
    return InMemoryContactsRepo()


@pytest.fixture
def owners() -> StubOwners:
    return StubOwners()


@pytest.fixture
def account_settings() -> StubSettings:
    return StubSettings()


@pytest.fixture
def service(
    account_settings: StubSettings, owners: StubOwners, repo: InMemoryContactsRepo
) -> ContactsService:
    return ContactsService(clock=lambda: NOW, owners=owners, repo=repo, settings=account_settings)


@pytest.fixture
async def provisioned(service: ContactsService) -> ContactsService:
    await service.provision_defaults(ACCOUNT, NOW)
    return service


@pytest.fixture
async def example_list(provisioned: ContactsService) -> ContactList:
    lists = await provisioned.lists(ACCOUNT, None)
    return next(one for one in lists if one.kind is ListKind.STANDARD)


@pytest.fixture
async def opt_out_list(provisioned: ContactsService) -> ContactList:
    lists = await provisioned.lists(ACCOUNT, None)
    return next(one for one in lists if one.kind is ListKind.OPT_OUT)

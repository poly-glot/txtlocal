from dataclasses import dataclass

import pytest

from txtlocal.shared.testing import RecordingBus
from txtlocal.slices.automation.service import AutomationService
from txtlocal.slices.automation.tests.fakes import (
    ACCOUNT,
    NOW,
    InMemoryAutomationRepo,
    RecordingCampaigns,
    RecordingContacts,
    RecordingEmail,
    StubMessages,
    StubSenders,
)
from txtlocal.slices.contacts.model import ContactList, ListKind


@dataclass
class Ports:
    bus: RecordingBus
    campaigns: RecordingCampaigns
    contacts: RecordingContacts
    email: RecordingEmail
    messages: StubMessages
    repo: InMemoryAutomationRepo
    senders: StubSenders


@pytest.fixture
def ports() -> Ports:
    return Ports(
        bus=RecordingBus(),
        campaigns=RecordingCampaigns(),
        contacts=RecordingContacts(),
        email=RecordingEmail(),
        messages=StubMessages(),
        repo=InMemoryAutomationRepo(),
        senders=StubSenders(),
    )


@pytest.fixture
def bus(ports: Ports) -> RecordingBus:
    return ports.bus


@pytest.fixture
def campaigns(ports: Ports) -> RecordingCampaigns:
    return ports.campaigns


@pytest.fixture
def contacts(ports: Ports) -> RecordingContacts:
    return ports.contacts


@pytest.fixture
def email(ports: Ports) -> RecordingEmail:
    return ports.email


@pytest.fixture
def messages(ports: Ports) -> StubMessages:
    return ports.messages


@pytest.fixture
def repo(ports: Ports) -> InMemoryAutomationRepo:
    return ports.repo


@pytest.fixture
def senders(ports: Ports) -> StubSenders:
    return ports.senders


@pytest.fixture
def service(ports: Ports) -> AutomationService:
    return AutomationService(
        bus=ports.bus,
        campaigns=ports.campaigns,
        clock=lambda: NOW,
        contacts=ports.contacts,
        email=ports.email,
        messages=ports.messages,
        repo=ports.repo,
        senders=ports.senders,
    )


@pytest.fixture
def opt_out_list() -> ContactList:
    return ContactList(
        created_at=NOW, kind=ListKind.OPT_OUT, list_id="optout-1", name="Opt-Out List"
    )


@pytest.fixture
async def provisioned(
    service: AutomationService, contacts: RecordingContacts, opt_out_list: ContactList
) -> AutomationService:
    contacts.list_rows[ACCOUNT] = [opt_out_list]
    await service.provision_defaults(ACCOUNT, NOW)
    return service

import pytest

from txtlocal.slices.inbox.service import InboxService
from txtlocal.slices.inbox.tests.fakes import (
    NOW,
    InMemoryInboxRepo,
    ScriptedMessaging,
    ScriptedNames,
    ScriptedQuickSend,
)


@pytest.fixture
def repo() -> InMemoryInboxRepo:
    return InMemoryInboxRepo()


@pytest.fixture
def names() -> ScriptedNames:
    return ScriptedNames()


@pytest.fixture
def messaging() -> ScriptedMessaging:
    return ScriptedMessaging()


@pytest.fixture
def quick_send() -> ScriptedQuickSend:
    return ScriptedQuickSend()


@pytest.fixture
def service(
    repo: InMemoryInboxRepo,
    names: ScriptedNames,
    messaging: ScriptedMessaging,
    quick_send: ScriptedQuickSend,
) -> InboxService:
    return InboxService(
        clock=lambda: NOW, contacts=names, messaging=messaging, quick_send=quick_send, repo=repo
    )

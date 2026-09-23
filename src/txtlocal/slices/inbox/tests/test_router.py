from http import HTTPStatus

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from txtlocal.shared.bus import Topic
from txtlocal.shared.errors import BadRequest, NotFound
from txtlocal.shared.testing import RecordingBus
from txtlocal.slices.identity.model import Principal, Role
from txtlocal.slices.inbox.model import ProviderInboundSms
from txtlocal.slices.inbox.router import CONVERSATIONS_PREFIX, build_demo_router, build_router
from txtlocal.slices.inbox.service import CONVERSATION_NOT_FOUND, InboxService
from txtlocal.slices.inbox.tests.fakes import (
    ACCOUNT,
    NOW,
    OTHER_PEER,
    PEER,
    SENDER_ID,
    ScriptedMessaging,
    ScriptedNames,
    ScriptedQuickSend,
    inbound_of,
    message_row_of,
)

PRINCIPAL = Principal(
    account_id=ACCOUNT, role=Role.OWNER, user_id="user-1", username="demo@txtlocal.local"
)


async def fixed_principal(_request: Request) -> Principal:
    return PRINCIPAL


@pytest.fixture
def client(service: InboxService) -> TestClient:
    app = FastAPI()
    app.include_router(build_router(service, fixed_principal))
    return TestClient(app)


async def test_get_conversations_lists_newest_first_with_resolved_names(
    client: TestClient, service: InboxService, names: ScriptedNames
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(peer=PEER), SENDER_ID, NOW)
    names.known[PEER] = "Jane Doe"

    response = client.get(CONVERSATIONS_PREFIX)

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["nextCursor"] is None
    [item] = body["items"]
    assert item["peer"] == PEER
    assert item["name"] == "Jane Doe"
    assert item["unread"] == 1
    assert item["status"] == "OPEN"
    assert item["lastDirection"] == "IN"
    assert item["lastPreview"] == "hello"


async def test_get_conversations_filters_by_status_query_param(
    client: TestClient, service: InboxService
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(peer=PEER), SENDER_ID, NOW)

    response = client.get(CONVERSATIONS_PREFIX, params={"status": "CLOSED"})

    assert response.status_code == HTTPStatus.OK
    assert response.json()["items"] == []


async def test_get_thread_returns_conversation_messages_and_hint(
    client: TestClient, service: InboxService, messaging: ScriptedMessaging
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(), SENDER_ID, NOW)
    messaging.messages[(ACCOUNT, PEER)] = [message_row_of()]

    response = client.get(f"{CONVERSATIONS_PREFIX}/{PEER}")

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["conversation"]["peer"] == PEER
    [message] = body["messages"]["items"]
    assert message["messageId"] == "message-1"
    assert body["messages"]["nextCursor"] is None
    assert body["replyHint"] == (
        "Replies to this number reach you only when the contact replies to your last message"
    )


def test_get_thread_unknown_peer_raises_not_found(client: TestClient) -> None:
    with pytest.raises(NotFound) as caught:
        client.get(f"{CONVERSATIONS_PREFIX}/{PEER}")
    assert str(caught.value) == CONVERSATION_NOT_FOUND


def test_post_messages_replies_and_returns_the_campaign(
    client: TestClient, quick_send: ScriptedQuickSend
) -> None:
    response = client.post(
        f"{CONVERSATIONS_PREFIX}/{PEER}/messages", json={"body": "hi there", "senderId": SENDER_ID}
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["campaignId"] == quick_send.result.campaign_id
    [(_, request, _)] = quick_send.calls
    assert request.sender_id == SENDER_ID


def test_post_messages_refusal_surfaces_the_policy_message_verbatim(
    client: TestClient, quick_send: ScriptedQuickSend
) -> None:
    quick_send.refusal = BadRequest("This contact has opted out")

    with pytest.raises(BadRequest) as caught:
        client.post(f"{CONVERSATIONS_PREFIX}/{PEER}/messages", json={"body": "hi"})
    assert str(caught.value) == "This contact has opted out"


async def test_post_read_marks_the_conversation_read(
    client: TestClient, service: InboxService
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(), SENDER_ID, NOW)

    response = client.post(f"{CONVERSATIONS_PREFIX}/{PEER}/read")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["unread"] == 0


@pytest.mark.parametrize(
    ("path", "expected"),
    [("close", "CLOSED"), ("reopen", "OPEN")],
    ids=["close-sets-closed", "reopen-sets-open"],
)
async def test_post_close_and_reopen_set_status(
    client: TestClient, service: InboxService, path: str, expected: str
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(), SENDER_ID, NOW)

    response = client.post(f"{CONVERSATIONS_PREFIX}/{PEER}/{path}")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["status"] == expected


async def test_post_read_all_marks_every_conversation_read(
    client: TestClient, service: InboxService
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(peer=PEER), SENDER_ID, NOW)
    await service.note_inbound(ACCOUNT, inbound_of(peer=OTHER_PEER), SENDER_ID, NOW)

    response = client.post(f"{CONVERSATIONS_PREFIX}/read-all")

    assert response.status_code == HTTPStatus.NO_CONTENT
    listed = client.get(CONVERSATIONS_PREFIX).json()["items"]
    assert [item["unread"] for item in listed] == [0, 0]


def test_demo_inbound_publishes_the_provider_shaped_json() -> None:
    bus = RecordingBus()
    app = FastAPI()
    app.include_router(build_demo_router(bus))
    client = TestClient(app)

    response = client.post(
        "/api/app/demo/inbound", json={"from": PEER, "to": "+447984390718", "body": "hello"}
    )

    assert response.status_code == HTTPStatus.ACCEPTED
    [(topic, body)] = bus.published
    assert topic is Topic.SMS_INBOUND
    provider = ProviderInboundSms.model_validate_json(body)
    assert provider.origination_number == PEER
    assert provider.destination_number == "+447984390718"
    assert provider.message_body == "hello"
    assert provider.previous_published_message_id is None

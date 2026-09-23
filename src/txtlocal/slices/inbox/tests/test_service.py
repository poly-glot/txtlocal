import pytest

from txtlocal.shared.errors import BadRequest, NotFound
from txtlocal.slices.identity.model import Role
from txtlocal.slices.inbox.model import Conversation, ConversationStatus, ReplyRequest
from txtlocal.slices.inbox.service import (
    CONVERSATION_NOT_FOUND,
    InboxService,
    matches,
    preview_of,
    system_principal,
)
from txtlocal.slices.inbox.tests.fakes import (
    ACCOUNT,
    LATER,
    NOW,
    OTHER_PEER,
    PEER,
    SENDER_ID,
    InMemoryInboxRepo,
    ScriptedMessaging,
    ScriptedNames,
    ScriptedQuickSend,
    inbound_of,
    message_row_of,
)
from txtlocal.slices.messaging.model import Direction, MessageType

SHARED_NUMBER_HINT = (
    "Replies to this number reach you only when the contact replies to your last message"
)


async def test_note_inbound_to_unknown_peer_creates_conversation_with_unread_one(
    service: InboxService, repo: InMemoryInboxRepo
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(), SENDER_ID, NOW)

    conversation = await repo.get(ACCOUNT, PEER)

    assert conversation is not None
    assert conversation.unread == 1
    assert conversation.last_direction is Direction.IN
    assert conversation.last_preview == "hello"
    assert conversation.last_sender_id == SENDER_ID
    assert conversation.status is ConversationStatus.OPEN


async def test_note_inbound_again_increments_unread(
    service: InboxService, repo: InMemoryInboxRepo
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(), SENDER_ID, NOW)
    await service.note_inbound(ACCOUNT, inbound_of(), SENDER_ID, LATER)

    conversation = await repo.get(ACCOUNT, PEER)

    assert conversation is not None
    assert conversation.unread == 2


async def test_close_then_inbound_reopens(service: InboxService, repo: InMemoryInboxRepo) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(), SENDER_ID, NOW)
    await service.close(ACCOUNT, PEER)

    await service.note_inbound(ACCOUNT, inbound_of(), SENDER_ID, LATER)

    conversation = await repo.get(ACCOUNT, PEER)
    assert conversation is not None
    assert conversation.status is ConversationStatus.OPEN


async def test_note_outbound_does_not_change_unread(
    service: InboxService, repo: InMemoryInboxRepo
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(), SENDER_ID, NOW)

    await service.note_outbound(ACCOUNT, PEER, SENDER_ID, "reply preview", LATER)

    conversation = await repo.get(ACCOUNT, PEER)
    assert conversation is not None
    assert conversation.unread == 1
    assert conversation.last_direction is Direction.OUT
    assert conversation.last_preview == "reply preview"


async def test_note_outbound_creates_conversation_for_a_new_peer(
    service: InboxService, repo: InMemoryInboxRepo
) -> None:
    await service.note_outbound(ACCOUNT, PEER, SENDER_ID, "hello there", NOW)

    conversation = await repo.get(ACCOUNT, PEER)
    assert conversation is not None
    assert conversation.unread == 0
    assert conversation.status is ConversationStatus.OPEN


@pytest.mark.parametrize(
    ("known", "expected"),
    [({PEER: "Jane Doe"}, "Jane Doe"), ({}, PEER)],
    ids=["name-resolves", "falls-back-to-number"],
)
async def test_list_conversations_resolves_name(
    service: InboxService,
    names: ScriptedNames,
    known: dict[str, str],
    expected: str,
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(), SENDER_ID, NOW)
    names.known.update(known)

    page = await service.list_conversations(ACCOUNT, None, None, None)

    [view] = page.items
    assert view.name == expected


async def test_list_conversations_filters_by_status(service: InboxService) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(peer=PEER), SENDER_ID, NOW)
    await service.note_inbound(ACCOUNT, inbound_of(peer=OTHER_PEER), SENDER_ID, LATER)
    await service.close(ACCOUNT, PEER)

    open_page = await service.list_conversations(ACCOUNT, ConversationStatus.OPEN, None, None)
    closed_page = await service.list_conversations(ACCOUNT, ConversationStatus.CLOSED, None, None)

    assert [view.peer for view in open_page.items] == [OTHER_PEER]
    assert [view.peer for view in closed_page.items] == [PEER]


async def test_list_conversations_search_matches_name_prefix(
    service: InboxService, names: ScriptedNames
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(peer=PEER), SENDER_ID, NOW)
    await service.note_inbound(ACCOUNT, inbound_of(peer=OTHER_PEER), SENDER_ID, LATER)
    names.known[PEER] = "Jane Doe"

    page = await service.list_conversations(ACCOUNT, None, "jane", None)

    assert [view.peer for view in page.items] == [PEER]


async def test_list_conversations_search_matches_number_prefix(service: InboxService) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(peer=PEER), SENDER_ID, NOW)
    await service.note_inbound(ACCOUNT, inbound_of(peer=OTHER_PEER), SENDER_ID, LATER)

    page = await service.list_conversations(ACCOUNT, None, "+44741", None)

    assert [view.peer for view in page.items] == [PEER]


async def test_thread_returns_conversation_messages_and_hint_verbatim(
    service: InboxService, messaging: ScriptedMessaging
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(), SENDER_ID, NOW)
    row = message_row_of()
    messaging.messages[(ACCOUNT, PEER)] = [row]

    result = await service.thread(ACCOUNT, PEER, None)

    assert result.conversation.peer == PEER
    assert result.messages.items == [row]
    assert result.reply_hint == SHARED_NUMBER_HINT


async def test_thread_unknown_peer_raises_not_found(service: InboxService) -> None:
    with pytest.raises(NotFound) as caught:
        await service.thread(ACCOUNT, PEER, None)
    assert str(caught.value) == CONVERSATION_NOT_FOUND


async def test_reply_sends_from_the_chosen_sender(
    service: InboxService, quick_send: ScriptedQuickSend
) -> None:
    result = await service.reply(ACCOUNT, PEER, ReplyRequest(body="hi", sender_id=SENDER_ID))

    assert result == quick_send.result
    [(principal, request, now)] = quick_send.calls
    assert (principal.account_id, principal.role, principal.user_id, principal.username) == (
        ACCOUNT,
        Role.OWNER,
        "system",
        "inbox",
    )
    assert (request.body, request.message_type, request.sender_id, request.to) == (
        "hi",
        MessageType.TRANSACTIONAL,
        SENDER_ID,
        [PEER],
    )
    assert now == NOW


async def test_reply_without_a_sender_leaves_the_choice_to_smart_senders(
    service: InboxService, quick_send: ScriptedQuickSend
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(), SENDER_ID, NOW)

    await service.reply(ACCOUNT, PEER, ReplyRequest(body="hi"))

    [(_, request, _)] = quick_send.calls
    assert request.sender_id is None


async def test_reply_refusal_surfaces_the_policy_message_verbatim(
    service: InboxService, quick_send: ScriptedQuickSend
) -> None:
    quick_send.refusal = BadRequest("This contact has opted out")

    with pytest.raises(BadRequest) as caught:
        await service.reply(ACCOUNT, PEER, ReplyRequest(body="hi"))
    assert str(caught.value) == "This contact has opted out"


async def test_mark_read_zeroes_unread(service: InboxService) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(), SENDER_ID, NOW)

    view = await service.mark_read(ACCOUNT, PEER)

    assert view.unread == 0


async def test_mark_read_unknown_peer_raises_not_found(service: InboxService) -> None:
    with pytest.raises(NotFound) as caught:
        await service.mark_read(ACCOUNT, PEER)
    assert str(caught.value) == CONVERSATION_NOT_FOUND


@pytest.mark.parametrize(
    ("action", "expected"),
    [("close", ConversationStatus.CLOSED), ("reopen", ConversationStatus.OPEN)],
    ids=["close-sets-closed", "reopen-sets-open"],
)
async def test_close_and_reopen_set_status(
    service: InboxService, action: str, expected: ConversationStatus
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(), SENDER_ID, NOW)

    view = await getattr(service, action)(ACCOUNT, PEER)

    assert view.status is expected


@pytest.mark.parametrize("action", ["close", "reopen"], ids=["close", "reopen"])
async def test_close_and_reopen_unknown_peer_raises_not_found(
    service: InboxService, action: str
) -> None:
    with pytest.raises(NotFound) as caught:
        await getattr(service, action)(ACCOUNT, PEER)
    assert str(caught.value) == CONVERSATION_NOT_FOUND


async def test_mark_all_read_zeroes_every_conversation(
    service: InboxService, repo: InMemoryInboxRepo
) -> None:
    await service.note_inbound(ACCOUNT, inbound_of(peer=PEER), SENDER_ID, NOW)
    await service.note_inbound(ACCOUNT, inbound_of(peer=OTHER_PEER), SENDER_ID, LATER)

    await service.mark_all_read(ACCOUNT)

    first = await repo.get(ACCOUNT, PEER)
    second = await repo.get(ACCOUNT, OTHER_PEER)
    assert first is not None
    assert second is not None
    assert (first.unread, second.unread) == (0, 0)


@pytest.mark.parametrize(
    ("body", "expected"),
    [("short body", "short body"), ("x" * 90, "x" * 80)],
    ids=["under-length-kept-whole", "truncated-to-80-characters"],
)
def test_preview_of(body: str, expected: str) -> None:
    assert preview_of(body) == expected


@pytest.mark.parametrize(
    ("name", "needle", "expected"),
    [
        (PEER, "+44741", True),
        ("Jane Doe", "jane", True),
        ("Jane Doe", "999", False),
    ],
    ids=["number-prefix-matches", "name-prefix-is-case-insensitive", "no-match"],
)
def test_matches(name: str, needle: str, expected: bool) -> None:
    conversation = Conversation(
        last_at=NOW, last_direction=Direction.IN, last_preview="", peer=PEER, unread=0
    )
    assert matches(conversation, name, needle) is expected


def test_system_principal_stamps_the_audit_fields() -> None:
    principal = system_principal(ACCOUNT)

    assert (principal.account_id, principal.role, principal.user_id, principal.username) == (
        ACCOUNT,
        Role.OWNER,
        "system",
        "inbox",
    )

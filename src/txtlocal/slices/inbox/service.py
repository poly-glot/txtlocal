from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

from txtlocal.shared.errors import NotFound
from txtlocal.slices.billing.model import Page
from txtlocal.slices.identity.model import Principal, Role
from txtlocal.slices.inbox.model import (
    Conversation,
    ConversationStatus,
    ConversationView,
    ReplyRequest,
    ThreadPage,
)
from txtlocal.slices.messaging.model import (
    InboundMessage,
    MessageRow,
    MessageType,
    QuickSendRequest,
)

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock
    from txtlocal.shared.phone import E164
    from txtlocal.slices.campaigns.model import QuickSendResult
    from txtlocal.slices.inbox.repo import InboxRepo

CONVERSATION_NOT_FOUND = "Conversation not found"
PAGE_SIZE = 20
PREVIEW_LENGTH = 80
SEARCH_LIMIT = 200
SHARED_NUMBER_HINT = (
    "Replies to this number reach you only when the contact replies to your last message"
)
SYSTEM_USER_ID = "system"
SYSTEM_USERNAME = "inbox"


class Names(Protocol):
    async def names_of(self, account_id: str, peers: Sequence[E164]) -> dict[E164, str]: ...


class Messaging(Protocol):
    async def conversation_messages(
        self, account_id: str, peer: E164, cursor: str | None
    ) -> Page[MessageRow]: ...


class QuickSend(Protocol):
    async def send_quick(
        self, principal: Principal, request: QuickSendRequest, now: datetime
    ) -> QuickSendResult: ...


def preview_of(body: str) -> str:
    return body[:PREVIEW_LENGTH]


def system_principal(account_id: str) -> Principal:
    return Principal(
        account_id=account_id, role=Role.OWNER, user_id=SYSTEM_USER_ID, username=SYSTEM_USERNAME
    )


def matches(conversation: Conversation, name: str, needle: str) -> bool:
    if conversation.peer.startswith(needle):
        return True
    return name.casefold().startswith(needle.casefold())


@dataclass(frozen=True, slots=True)
class InboxService:
    clock: Clock
    contacts: Names
    messaging: Messaging
    quick_send: QuickSend
    repo: InboxRepo

    async def list_conversations(
        self,
        account_id: str,
        status: ConversationStatus | None,
        q: str | None,
        cursor: str | None,
    ) -> Page[ConversationView]:
        needle = (q or "").strip()
        batch = (
            await self.repo.list_conversations(account_id, status, None, SEARCH_LIMIT)
            if needle
            else await self.repo.list_conversations(account_id, status, cursor, PAGE_SIZE)
        )

        names = await self.contacts.names_of(account_id, [one.peer for one in batch.items])
        found = [
            one
            for one in batch.items
            if not needle or matches(one, names.get(one.peer, one.peer), needle)
        ]
        views = [ConversationView.of(one, names.get(one.peer, one.peer)) for one in found]
        next_cursor = None if needle else batch.next_cursor
        return Page[ConversationView](items=views, next_cursor=next_cursor)

    async def thread(self, account_id: str, peer: E164, cursor: str | None) -> ThreadPage:
        conversation = await self._get(account_id, peer)
        names = await self.contacts.names_of(account_id, [peer])
        page = await self.messaging.conversation_messages(account_id, peer, cursor)

        return ThreadPage(
            conversation=ConversationView.of(conversation, names.get(peer, peer)),
            messages=page,
            reply_hint=SHARED_NUMBER_HINT,
        )

    async def reply(self, account_id: str, peer: E164, request: ReplyRequest) -> QuickSendResult:
        quick_request = QuickSendRequest(
            body=request.body,
            message_type=MessageType.TRANSACTIONAL,
            sender_id=request.sender_id,
            to=[peer],
        )
        return await self.quick_send.send_quick(
            system_principal(account_id), quick_request, self.clock()
        )

    async def mark_read(self, account_id: str, peer: E164) -> ConversationView:
        if not await self.repo.mark_read(account_id, peer):
            raise NotFound(CONVERSATION_NOT_FOUND)
        return await self._view(account_id, peer)

    async def close(self, account_id: str, peer: E164) -> ConversationView:
        if not await self.repo.set_status(account_id, peer, ConversationStatus.CLOSED):
            raise NotFound(CONVERSATION_NOT_FOUND)
        return await self._view(account_id, peer)

    async def reopen(self, account_id: str, peer: E164) -> ConversationView:
        if not await self.repo.set_status(account_id, peer, ConversationStatus.OPEN):
            raise NotFound(CONVERSATION_NOT_FOUND)
        return await self._view(account_id, peer)

    async def mark_all_read(self, account_id: str) -> None:
        await self.repo.mark_all_read(account_id)

    async def note_inbound(
        self, account_id: str, inbound: InboundMessage, sender_id: str | None, now: datetime
    ) -> None:
        await self.repo.upsert_inbound(
            account_id, inbound.peer, preview_of(inbound.body), sender_id, now
        )

    async def note_outbound(
        self, account_id: str, peer: E164, sender_id: str, preview: str, now: datetime
    ) -> None:
        await self.repo.upsert_outbound(account_id, peer, preview, sender_id, now)

    async def _get(self, account_id: str, peer: E164) -> Conversation:
        conversation = await self.repo.get(account_id, peer)
        if conversation is None:
            raise NotFound(CONVERSATION_NOT_FOUND)
        return conversation

    async def _view(self, account_id: str, peer: E164) -> ConversationView:
        conversation = await self._get(account_id, peer)
        names = await self.contacts.names_of(account_id, [peer])
        return ConversationView.of(conversation, names.get(peer, peer))

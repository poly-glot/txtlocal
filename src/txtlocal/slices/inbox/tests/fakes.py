from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from txtlocal.shared.money import Micro
from txtlocal.shared.phone import E164
from txtlocal.slices.billing.model import Page
from txtlocal.slices.campaigns.model import QuickSendResult
from txtlocal.slices.inbox.model import Conversation, ConversationStatus
from txtlocal.slices.messaging.model import (
    Direction,
    InboundMessage,
    MessageRow,
    MessageStatus,
    Product,
)
from txtlocal.slices.messaging.segments import Encoding

if TYPE_CHECKING:
    from txtlocal.shared.errors import AppError
    from txtlocal.slices.identity.model import Principal
    from txtlocal.slices.messaging.model import QuickSendRequest

ACCOUNT = "account-1"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 19, 12, 5, tzinfo=UTC)
PEER = E164("+447411972333")
OTHER_PEER = E164("+447900555111")
SENDER_NUMBER = E164("+447984390718")
SENDER_ID = "sender-1"


def inbound_of(peer: E164 = PEER, body: str = "hello") -> InboundMessage:
    return InboundMessage(
        body=body,
        destination=SENDER_NUMBER,
        inbound_message_id="inbound-1",
        keyword="",
        peer=peer,
        previous_published_message_id=None,
        received_at=NOW,
    )


def message_row_of() -> MessageRow:
    return MessageRow(
        account_id=ACCOUNT,
        body="hi",
        campaign_id="campaign-1",
        country="GB",
        direction=Direction.OUT,
        encoding=Encoding.GSM7,
        from_=SENDER_NUMBER,
        kind=Product.SMS,
        message_id="message-1",
        parts=1,
        price_micro=Micro(42700),
        queued_at=NOW,
        status=MessageStatus.SENT,
        to=PEER,
        user_id="user-1",
        username="demo@txtlocal.local",
    )


@dataclass
class InMemoryInboxRepo:
    conversations: dict[tuple[str, str], Conversation] = field(default_factory=dict)

    async def get(self, account_id: str, peer: E164) -> Conversation | None:
        return self.conversations.get((account_id, peer))

    async def list_conversations(
        self,
        account_id: str,
        status: ConversationStatus | None,
        cursor: str | None,
        limit: int,
    ) -> Page[Conversation]:
        del cursor
        items = [c for (owner, _), c in self.conversations.items() if owner == account_id]
        if status is not None:
            items = [c for c in items if c.status is status]
        items.sort(key=lambda c: c.last_at, reverse=True)
        return Page[Conversation](items=items[:limit], next_cursor=None)

    async def mark_all_read(self, account_id: str) -> None:
        for key, conversation in list(self.conversations.items()):
            if key[0] == account_id and conversation.unread:
                self.conversations[key] = conversation.model_copy(update={"unread": 0})

    async def mark_read(self, account_id: str, peer: E164) -> bool:
        current = self.conversations.get((account_id, peer))
        if current is None:
            return False
        self.conversations[(account_id, peer)] = current.model_copy(update={"unread": 0})
        return True

    async def set_status(self, account_id: str, peer: E164, status: ConversationStatus) -> bool:
        current = self.conversations.get((account_id, peer))
        if current is None:
            return False
        self.conversations[(account_id, peer)] = current.model_copy(update={"status": status})
        return True

    async def upsert_inbound(
        self, account_id: str, peer: E164, preview: str, sender_id: str | None, now: datetime
    ) -> None:
        current = self.conversations.get((account_id, peer))
        unread = (current.unread if current is not None else 0) + 1
        sender = sender_id if sender_id is not None else _prior_sender(current)
        self.conversations[(account_id, peer)] = Conversation(
            last_at=now,
            last_direction=Direction.IN,
            last_preview=preview,
            last_sender_id=sender,
            peer=peer,
            status=ConversationStatus.OPEN,
            unread=unread,
        )

    async def upsert_outbound(
        self, account_id: str, peer: E164, preview: str, sender_id: str, now: datetime
    ) -> None:
        current = self.conversations.get((account_id, peer))
        self.conversations[(account_id, peer)] = Conversation(
            last_at=now,
            last_direction=Direction.OUT,
            last_preview=preview,
            last_sender_id=sender_id,
            peer=peer,
            status=current.status if current is not None else ConversationStatus.OPEN,
            unread=current.unread if current is not None else 0,
        )


def _prior_sender(current: Conversation | None) -> str | None:
    return current.last_sender_id if current is not None else None


@dataclass
class ScriptedNames:
    known: dict[str, str] = field(default_factory=dict)

    async def names_of(self, account_id: str, peers: Sequence[E164]) -> dict[E164, str]:
        del account_id
        return {peer: self.known[peer] for peer in peers if peer in self.known}


@dataclass
class ScriptedMessaging:
    messages: dict[tuple[str, str], list[MessageRow]] = field(default_factory=dict)

    async def conversation_messages(
        self, account_id: str, peer: E164, cursor: str | None
    ) -> Page[MessageRow]:
        del cursor
        return Page[MessageRow](items=self.messages.get((account_id, peer), []), next_cursor=None)


@dataclass
class ScriptedQuickSend:
    result: QuickSendResult = field(
        default_factory=lambda: QuickSendResult(
            campaign_id="campaign-1", cost_micro=42700, recipients=1, refused=[]
        )
    )
    refusal: AppError | None = None
    calls: list[tuple[Principal, QuickSendRequest, datetime]] = field(default_factory=list)

    async def send_quick(
        self, principal: Principal, request: QuickSendRequest, now: datetime
    ) -> QuickSendResult:
        self.calls.append((principal, request, now))
        if self.refusal is not None:
            raise self.refusal
        return self.result

from enum import StrEnum
from typing import Self

from pydantic import Field

from txtlocal.shared.model import Model, Rfc3339
from txtlocal.shared.phone import E164
from txtlocal.slices.billing.model import Page
from txtlocal.slices.messaging.model import Direction, MessageRow


class ConversationStatus(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"


class Conversation(Model):
    last_at: Rfc3339
    last_direction: Direction
    last_preview: str
    last_sender_id: str | None = None
    peer: E164
    status: ConversationStatus = ConversationStatus.OPEN
    unread: int = 0


class ConversationView(Conversation):
    name: str

    @classmethod
    def of(cls, conversation: Conversation, name: str) -> Self:
        return cls(**conversation.model_dump(by_alias=False), name=name)


class ReplyRequest(Model):
    body: str
    sender_id: str | None = None


class DemoInboundRequest(Model):
    body: str
    from_: E164 = Field(alias="from")
    previous_message_id: str | None = None
    to: E164


class ProviderInboundSms(Model):
    destination_number: E164
    inbound_message_id: str
    message_body: str
    message_keyword: str | None = None
    origination_number: E164
    previous_published_message_id: str | None = None


class ThreadPage(Model):
    conversation: ConversationView
    messages: Page[MessageRow]
    reply_hint: str

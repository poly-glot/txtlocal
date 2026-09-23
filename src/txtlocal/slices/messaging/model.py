import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from random import Random
from typing import Literal, Self

from pydantic import Field

from txtlocal.shared.model import Model
from txtlocal.shared.money import Micro
from txtlocal.shared.phone import E164
from txtlocal.shared.table import partition, sort_ts
from txtlocal.slices.messaging.segments import MAX_CHARS, Encoding

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
MILLISECOND = timedelta(milliseconds=1)
KEY_SEPARATOR = "|"
MESSAGE_KEY = "messageKey"
QUICK_TTL_SECONDS = 3_600
CAMPAIGN_TTL_SECONDS = 86_400
TEMPLATE_NAME_MAX = 100
UUID_VERSION_7 = 7
RFC_4122_VARIANT = 0b10


class Product(StrEnum):
    MMS = "MMS"
    MMS_AS_LINK = "MMS_AS_LINK"
    SMS = "SMS"


class MessageType(StrEnum):
    PROMOTIONAL = "PROMOTIONAL"
    TRANSACTIONAL = "TRANSACTIONAL"


class MessageStatus(StrEnum):
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    QUEUED = "QUEUED"
    RECEIVED = "RECEIVED"
    SENT = "SENT"


type DeliveryStatus = Literal[MessageStatus.DELIVERED, MessageStatus.FAILED, MessageStatus.SENT]


class Direction(StrEnum):
    IN = "IN"
    OUT = "OUT"


class DispatchOutcome(StrEnum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    REFUSED = "REFUSED"


class RefusalReason(StrEnum):
    COUNTRY_NOT_ENABLED = "COUNTRY_NOT_ENABLED"
    DAILY_CAP = "DAILY_CAP"
    INSUFFICIENT_BALANCE = "INSUFFICIENT_BALANCE"
    NOT_VERIFIED = "NOT_VERIFIED"
    OPTED_OUT = "OPTED_OUT"
    SENDER_NOT_READY = "SENDER_NOT_READY"
    TRIAL_ENDED = "TRIAL_ENDED"


class SearchField(StrEnum):
    FROM = "FROM"
    TO = "TO"


class SendJob(Model):
    account_id: str
    body: str
    campaign_id: str
    country: str
    encoding: Encoding
    media_key: str | None = None
    message_type: MessageType
    origination: str
    parts: int
    price_micro: int
    product: Product
    sender_id: str
    sender_kind: str
    sender_value: str
    subject: str = ""
    to: str
    ttl_seconds: int = QUICK_TTL_SECONDS
    user_id: str
    username: str


@dataclass(frozen=True, slots=True)
class Dispatched:
    message_id: str
    outcome: DispatchOutcome
    failure_reason: str | None = None


class ProviderEvent(Model):
    context: dict[str, str]
    event_timestamp: datetime
    event_type: str
    message_id: str
    total_message_parts: int = 1
    total_message_price: float | None = None


@dataclass(frozen=True, slots=True)
class Transition:
    account_id: str
    campaign_id: str
    failure_reason: str | None
    message_id: str
    status: MessageStatus


@dataclass(frozen=True, slots=True)
class MessageRef:
    account_id: str
    campaign_id: str
    message_id: str
    peer: E164
    sender_id: str


@dataclass(frozen=True, slots=True)
class BodyQuote:
    chars: int
    encoding: Encoding
    parts: int


@dataclass(frozen=True, slots=True)
class MessageKey:
    pk: str
    sk: str

    @classmethod
    def parse(cls, text: str) -> Self | None:
        pk, separator, sk = text.partition(KEY_SEPARATOR)
        if not (separator and pk and sk):
            return None
        return cls(pk=pk, sk=sk)

    def __str__(self) -> str:
        return f"{self.pk}{KEY_SEPARATOR}{self.sk}"


@dataclass(frozen=True, slots=True)
class DeliveryUpdate:
    at: datetime
    event_type: str
    provider_message_id: str
    status: DeliveryStatus


class MessageRow(Model):
    account_id: str
    attempted_at: datetime | None = None
    body: str
    campaign_id: str
    country: str
    delivered_at: datetime | None = None
    direction: Direction
    encoding: Encoding
    failure_reason: str | None = None
    from_: str = Field(alias="from")
    kind: Product
    media_key: str | None = None
    message_id: str
    parts: int
    price_micro: Micro
    provider_message_id: str | None = None
    queued_at: datetime
    sender_id: str = ""
    sent_at: datetime | None = None
    status: MessageStatus
    subject: str | None = None
    to: E164
    user_id: str
    username: str

    @property
    def key(self) -> MessageKey:
        return message_key_for(self.account_id, self.message_id)


class HistoryQuery(Model):
    cursor: str | None = None
    field: SearchField = SearchField.TO
    kind: Product | None = None
    q: str | None = None
    since: date | None = Field(alias="from", default=None)
    until: date | None = Field(alias="to", default=None)


class HistoryPage(Model):
    cursor: str | None = None
    items: list[MessageRow]


class MediaUploadRequest(Model):
    content_type: str


class MediaUploadResponse(Model):
    key: str
    upload_url: str


class Template(Model):
    body: str
    created_at: datetime
    name: str
    template_id: str


class TemplateRequest(Model):
    body: str = Field(max_length=MAX_CHARS, min_length=1)
    name: str = Field(max_length=TEMPLATE_NAME_MAX, min_length=1)


class QuickSendRequest(Model):
    body: str
    kind: Product = Product.SMS
    list_ids: list[str] = Field(default_factory=list)
    media_key: str | None = None
    message_type: MessageType = MessageType.PROMOTIONAL
    send_at: datetime | None = None
    sender_id: str | None = None
    shorten_urls: bool = False
    subject: str = ""
    to: list[str]


class InboundMessage(Model):
    body: str
    destination: E164
    inbound_message_id: str
    keyword: str
    peer: E164
    previous_published_message_id: str | None = None
    received_at: datetime


def uuid7_at(moment: datetime, rng: Random) -> uuid.UUID:
    millis = (moment - EPOCH) // MILLISECOND
    value = (
        (millis << 80)
        | (UUID_VERSION_7 << 76)
        | (rng.getrandbits(12) << 64)
        | (RFC_4122_VARIANT << 62)
        | rng.getrandbits(62)
    )
    return uuid.UUID(int=value)


def minted_at(message_id: str) -> datetime:
    return EPOCH + uuid.UUID(message_id).time * MILLISECOND


def month_of(moment: datetime) -> str:
    return f"{moment.astimezone(UTC):%Y-%m}"


def message_partition(account_id: str, month: str) -> str:
    return partition("ACCOUNT", f"{account_id}#MSG#{month}")


def message_key_for(account_id: str, message_id: str) -> MessageKey:
    minted = minted_at(message_id)
    return MessageKey(
        pk=message_partition(account_id, month_of(minted)),
        sk=f"{sort_ts(minted)}#{message_id}",
    )

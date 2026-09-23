from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import Field

from txtlocal.shared.model import Model, Rfc3339
from txtlocal.shared.money import Micro
from txtlocal.shared.phone import E164
from txtlocal.slices.messaging.model import Product, RefusalReason

UNPRICED = Micro(0)


class CampaignKind(StrEnum):
    LIST = "LIST"
    QUICK = "QUICK"


class CampaignStatus(StrEnum):
    CANCELLED = "CANCELLED"
    DRAFT = "DRAFT"
    FAILED = "FAILED"
    SCHEDULED = "SCHEDULED"
    SENDING = "SENDING"
    SENT = "SENT"


class CampaignCounter(StrEnum):
    DELIVERED = "delivered"
    REFUSED = "refused"
    SENT = "sent"
    UNDELIVERED = "undelivered"


class OptOutMode(StrEnum):
    REPLY_STOP = "REPLY_STOP"
    UNSUBSCRIBE_LINK = "UNSUBSCRIBE_LINK"


class CampaignCounts(Model):
    delivered: int = 0
    queued: int = 0
    recipients: int
    refused: int = 0
    sent: int = 0
    undelivered: int = 0


class Campaign(Model):
    body: str
    campaign_id: str
    channel: Product
    claimed_at: Rfc3339 | None = None
    completed_at: Rfc3339 | None = None
    counts: CampaignCounts
    created_at: Rfc3339
    fanout_cursor: str | None = None
    footer: str = ""
    kind: CampaignKind
    last_progress_at: Rfc3339 | None = None
    list_id: str | None = None
    list_ids: list[str] = Field(default_factory=list)
    media_key: str | None = None
    name: str
    opt_out_mode: OptOutMode = OptOutMode.REPLY_STOP
    quote_micro: Micro
    recipients: list[E164]
    reserved_micro: Micro
    scheduled_at: Rfc3339 | None = None
    sender_id: str
    settled_micro: Micro | None = None
    shorten_urls: bool
    status: CampaignStatus
    subject: str | None = None
    user_id: str
    username: str


class CampaignDraft(Model):
    body: str = ""
    footer: str = ""
    list_id: str | None = None
    list_ids: list[str] = Field(default_factory=list)
    media_key: str | None = None
    name: str = ""
    opt_out_mode: OptOutMode = OptOutMode.REPLY_STOP
    product: Product = Product.SMS
    sender_id: str = ""
    shorten_urls: bool = False
    subject: str | None = None


class CampaignQuery(Model):
    cursor: str | None = None
    kind: Product | None = None
    q: str | None = None


class CampaignQuote(Model):
    cost_micro: Micro
    parts: int
    recipients: int
    sender_display: str


class CampaignReport(Model):
    campaign: Campaign
    clicks: int = 0


class CampaignPage(Model):
    cursor: str | None = None
    items: list[Campaign]


class ScheduleRequest(Model):
    now: bool = False
    send_at: datetime | None = None


class Refusal(Model):
    message: str
    reason: RefusalReason
    to: E164


class QuickQuote(Model):
    cost_micro: int
    parts: int
    recipients: int
    refused: list[Refusal]


class QuickSendResult(Model):
    campaign_id: str
    cost_micro: int
    recipients: int
    refused: list[Refusal]


@dataclass(frozen=True, slots=True)
class CampaignRef:
    account_id: str
    campaign_id: str


@dataclass(frozen=True, slots=True)
class FanOut:
    campaign_id: str
    queued: int = 0
    recipients: int = 0
    skipped: bool = False


@dataclass(frozen=True, slots=True)
class FanoutStep:
    at: datetime
    cursor: str | None
    queued: int
    recipients: int
    refused: int


@dataclass(frozen=True, slots=True)
class Settled:
    campaign_id: str
    missing: int = 0
    settled_micro: Micro = UNPRICED
    skipped: bool = False


@dataclass(frozen=True, slots=True)
class SchedulePlan:
    quote_micro: Micro
    recipients: int
    reserved_micro: Micro
    scheduled_at: datetime

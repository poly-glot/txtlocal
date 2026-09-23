from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from pydantic import Field

from txtlocal.shared.model import Model
from txtlocal.slices.messaging.model import Direction, MessageStatus, Product
from txtlocal.slices.messaging.segments import Encoding

DEFAULT_LIMIT = 20
MAX_LIMIT = 100
MIN_LIMIT = 1

MAX_CONTACTS_BATCH = 1_000
MAX_CUSTOM_STRING = 100
MAX_MESSAGES = 1_000
MAX_MMS_BODY = 1_500
MAX_SUBJECT = 40
MIN_MESSAGES = 1


class IdempotencyStatus(StrEnum):
    DONE = "DONE"
    IN_FLIGHT = "IN_FLIGHT"


class V3HistoryStatus(StrEnum):
    CANCELLED = "CANCELLED"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    QUEUED = "QUEUED"
    RECEIVED = "RECEIVED"
    SCHEDULED = "SCHEDULED"
    SENT = "SENT"


class V3SendMessage(Model):
    body: str
    custom_string: str | None = None
    from_: str | None = Field(alias="from", default=None)
    schedule: datetime | None = None
    to: str


class V3SendRequest(Model):
    messages: list[V3SendMessage]


class V3MmsMessage(Model):
    body: str
    custom_string: str | None = None
    from_: str | None = Field(alias="from", default=None)
    media_url: str
    schedule: datetime | None = None
    subject: str | None = None
    to: str


class V3MmsSendRequest(Model):
    messages: list[V3MmsMessage]


class V3SentMessage(Model):
    body: str
    country: str
    custom_string: str | None = None
    encoding: Encoding
    from_: str = Field(alias="from")
    message_id: str
    parts: int
    price: str
    product: Product
    schedule: datetime | None = None
    status: MessageStatus
    to: str


class V3SendResponse(Model):
    messages: list[V3SentMessage]
    total_price: str


class V3HistoryMessage(Model):
    body: str
    custom_string: str | None = None
    delivered_at: datetime | None = None
    direction: Direction
    failure_reason: str | None = None
    from_: str = Field(alias="from")
    message_id: str
    parts: int
    price: str
    sent_at: datetime | None = None
    status: MessageStatus
    to: str
    user_id: str


class V3HistoryQuery(Model):
    cursor: str | None = None
    direction: Direction | None = None
    limit: int = DEFAULT_LIMIT
    since: datetime | None = Field(alias="from", default=None)
    status: V3HistoryStatus | None = None
    until: datetime | None = Field(alias="to", default=None)


class V3HistoryPage(Model):
    messages: list[V3HistoryMessage]
    next_cursor: str | None = None


class V3Account(Model):
    account_id: str
    balance: str
    country: str
    currency: str
    email: str
    name: str
    trial_ends_at: datetime | None = None


class V3Balance(Model):
    balance: str
    currency: str


class V3ListRequest(Model):
    name: str


class V3List(Model):
    contact_count: int
    is_opt_out: bool
    list_id: str
    name: str
    updated_at: datetime


class V3ContactInput(Model):
    custom_fields: dict[str, str] = Field(default_factory=dict)
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    mobile: str


class V3Contact(Model):
    custom_fields: dict[str, str]
    email: str
    first_name: str
    last_name: str
    mobile: str


class V3ContactCreated(V3Contact):
    created: bool


class V3ContactPage(Model):
    contacts: list[V3Contact]
    next_cursor: str | None = None


class V3ContactBatch(Model):
    contacts: list[V3ContactInput]


class V3ContactBatchResult(Model):
    contacts: list[V3ContactCreated]


class V3SenderId(Model):
    countries: list[str]
    kind: str
    sender_id: str
    status: str
    value: str


class V3SenderIdsResponse(Model):
    senders: list[V3SenderId]


class V3Template(Model):
    body: str
    name: str
    template_id: str


class V3TemplatesResponse(Model):
    templates: list[V3Template]


class DeveloperGeneral(Model):
    base_url: str
    docs_url: str
    rate_limit_per_minute: int


class LogRow(Model):
    latency_ms: int
    method: str
    outcome: str
    request_id: str
    route: str
    status: int
    timestamp: datetime
    user_id: str


class LogTiles(Model):
    failed: int
    successful: int
    total: int


class LogsPage(Model):
    results_per_page: int = 20
    rows: list[LogRow]
    tiles: LogTiles


@dataclass(frozen=True, slots=True)
class LogFilters:
    outcome: str | None = None
    route: str | None = None
    user_id: str | None = None

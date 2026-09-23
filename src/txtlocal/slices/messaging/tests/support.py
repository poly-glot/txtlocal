from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from itertools import dropwhile
from operator import attrgetter, itemgetter
from random import Random
from typing import TYPE_CHECKING, ClassVar, assert_never

from txtlocal.shared.phone import E164
from txtlocal.slices.identity.model import Principal, Role
from txtlocal.slices.messaging.gateway import (
    PROVIDER_CAPABILITIES,
    Capabilities,
    Dispatch,
    MediaDispatch,
    MediaFile,
    MediaStorage,
    MediaUpload,
    Receipt,
)
from txtlocal.slices.messaging.model import (
    DeliveryStatus,
    DeliveryUpdate,
    InboundMessage,
    MessageKey,
    MessageRow,
    MessageStatus,
    MessageType,
    Product,
    SearchField,
    SendJob,
    Template,
    message_partition,
    uuid7_at,
)
from txtlocal.slices.messaging.policy import SendPolicy
from txtlocal.slices.messaging.segments import Encoding
from txtlocal.slices.messaging.service import MessagingService, inbound_row, queued_row

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock
    from txtlocal.shared.errors import AppError
    from txtlocal.slices.messaging.repo import HistoryWindow

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
ACCOUNT = "acct-1"
CAMPAIGN = "camp-1"
DESTINATION = E164("+447400123105")
TWO_WAY_NUMBER = E164("+447400900100")
PRINCIPAL = Principal(account_id=ACCOUNT, role=Role.OWNER, user_id="user-1", username="demo")
ALLOWED_COUNTRIES = frozenset({"GB", "US"})
DAILY_CAP = 500
MAX_PRICE_USD = "0.10"
MODE = "fake"
FAKE_CODE = "000000"


def clock_at(moment: datetime) -> Clock:
    return lambda: moment


def job(**overrides: object) -> SendJob:
    fields: dict[str, object] = {
        "account_id": ACCOUNT,
        "body": "Hello",
        "campaign_id": CAMPAIGN,
        "country": "GB",
        "encoding": Encoding.GSM7,
        "message_type": MessageType.PROMOTIONAL,
        "origination": "pool-1",
        "parts": 1,
        "price_micro": 42_700,
        "product": Product.SMS,
        "sender_id": "sender-1",
        "sender_kind": "SHARED",
        "sender_value": "SHARED",
        "to": DESTINATION,
        "user_id": "user-1",
        "username": "demo",
    }
    return SendJob.model_validate(fields | overrides)


def policy(*, daily_cap: int = DAILY_CAP, sandbox: bool = False) -> SendPolicy:
    return SendPolicy(
        allowed_countries=ALLOWED_COUNTRIES,
        daily_cap=daily_cap,
        max_price_usd=MAX_PRICE_USD,
        sandbox=sandbox,
    )


def row_at(moment: datetime, seed: int = 1, **overrides: object) -> MessageRow:
    return queued_row(job(**overrides), str(uuid7_at(moment, Random(seed))), moment)


def inbound(**overrides: object) -> InboundMessage:
    fields: dict[str, object] = {
        "body": "Hello",
        "destination": TWO_WAY_NUMBER,
        "inbound_message_id": "inbound-1",
        "keyword": "HELLO",
        "peer": DESTINATION,
        "previous_published_message_id": None,
        "received_at": NOW,
    }
    return InboundMessage.model_validate(fields | overrides)


def inbound_row_at(moment: datetime, seed: int = 1, **overrides: object) -> MessageRow:
    fields: dict[str, object] = {"received_at": moment} | overrides
    return inbound_row(inbound(**fields), ACCOUNT, str(uuid7_at(moment, Random(seed))))


def dispatch(destination: E164 = DESTINATION, body: str = "Hello") -> Dispatch:
    return Dispatch(
        body=body,
        destination=destination,
        max_price_usd=MAX_PRICE_USD,
        message_key="pk|sk",
        message_type=MessageType.PROMOTIONAL,
        origination="pool-1",
        ttl_seconds=3_600,
    )


def media_dispatch(destination: E164 = DESTINATION, subject: str = "") -> MediaDispatch:
    return MediaDispatch(
        body="Hello",
        destination=destination,
        max_price_usd=MAX_PRICE_USD,
        media_urls=("https://x/y.png",),
        message_key="pk|sk",
        message_type=MessageType.PROMOTIONAL,
        origination="pool-1",
        subject=subject,
        ttl_seconds=3_600,
    )


@dataclass
class RecordingGateway:
    clock: Clock
    failures: list[AppError] = field(default_factory=list)
    dispatches: list[Dispatch] = field(default_factory=list)
    started: set[E164] = field(default_factory=set)
    capabilities: ClassVar[Capabilities] = PROVIDER_CAPABILITIES

    async def send_text(self, dispatch: Dispatch) -> Receipt:
        return self._accept(dispatch)

    async def send_media(self, dispatch: MediaDispatch) -> Receipt:
        return self._accept(dispatch)

    async def start_verification(self, destination: E164) -> None:
        self.started.add(destination)

    async def check_verification(self, destination: E164, code: str) -> bool:
        return destination in self.started and code == FAKE_CODE

    def _accept(self, dispatch: Dispatch) -> Receipt:
        self.dispatches.append(dispatch)
        if self.failures:
            raise self.failures.pop(0)
        return Receipt(
            accepted_at=self.clock(), provider_message_id=f"provider-{len(self.dispatches)}"
        )


@dataclass
class FakeMediaStorage:
    files: dict[str, MediaFile] = field(default_factory=dict)
    minted: list[str] = field(default_factory=list)

    async def upload_url(self, content_type: str) -> MediaUpload:
        key = f"media-{len(self.minted) + 1}"
        self.minted.append(content_type)
        return MediaUpload(key=key, upload_url=self.public_url(key))

    def public_url(self, key: str) -> str:
        return f"https://x/{key}"

    async def store(self, key: str, content_type: str, body: bytes) -> None:
        self.files[key] = MediaFile(body=body, content_type=content_type)

    async def read(self, key: str) -> MediaFile | None:
        return self.files.get(key)


@dataclass
class OptOutSet:
    numbers: frozenset[E164]

    async def is_opted_out(self, account_id: str, destination: E164) -> bool:
        return account_id == ACCOUNT and destination in self.numbers


def admits(current: MessageStatus, incoming: DeliveryStatus) -> bool:
    match incoming:
        case MessageStatus.SENT:
            return current is MessageStatus.QUEUED
        case MessageStatus.DELIVERED | MessageStatus.FAILED:
            return current in {MessageStatus.QUEUED, MessageStatus.SENT}
        case _:
            assert_never(incoming)


def matches(window: HistoryWindow, row: MessageRow) -> bool:
    if window.number is not None:
        searched = row.to if window.field is SearchField.TO else row.from_
        if searched != window.number:
            return False
    return window.kind is None or row.kind.startswith(window.kind)


class InMemoryMessagingRepo:
    def __init__(self) -> None:
        self.rows: dict[MessageKey, MessageRow] = {}
        self.markers: dict[tuple[str, str, str], MessageKey] = {}
        self.inbound_markers: dict[tuple[str, str], MessageKey] = {}
        self.counts: Counter[tuple[str, date]] = Counter()
        self.templates: dict[tuple[str, str], Template] = {}

    def seed(self, *rows: MessageRow) -> None:
        for row in rows:
            self.rows[row.key] = row

    async def claim(self, row: MessageRow) -> bool:
        marker = (row.account_id, row.campaign_id, row.to)
        if marker in self.markers or row.key in self.rows:
            return False
        self.markers[marker] = row.key
        self.rows[row.key] = row
        return True

    async def claim_attempt(self, key: MessageKey, at: datetime) -> bool:
        row = self.rows.get(key)
        if row is None or row.status is not MessageStatus.QUEUED or row.attempted_at is not None:
            return False

        self.rows[key] = row.model_copy(update={"attempted_at": at})
        return True

    async def record_inbound(
        self, row: MessageRow, inbound_message_id: str, _now: datetime
    ) -> bool:
        marker = (row.account_id, inbound_message_id)
        if marker in self.inbound_markers or row.key in self.rows:
            return False
        self.inbound_markers[marker] = row.key
        self.rows[row.key] = row
        return True

    async def find_claim(
        self, account_id: str, campaign_id: str, destination: E164
    ) -> MessageKey | None:
        return self.markers.get((account_id, campaign_id, destination))

    async def find_by_provider_id(self, provider_message_id: str) -> MessageRow | None:
        for row in self.rows.values():
            if row.provider_message_id == provider_message_id:
                return row
        return None

    async def get(self, key: MessageKey) -> MessageRow | None:
        return self.rows.get(key)

    async def mark_sent(self, key: MessageKey, provider_message_id: str, sent_at: datetime) -> bool:
        row = self.rows.get(key)
        if row is None or row.status is not MessageStatus.QUEUED:
            return False
        self.rows[key] = row.model_copy(
            update={
                "provider_message_id": provider_message_id,
                "sent_at": sent_at,
                "status": MessageStatus.SENT,
            }
        )
        return True

    async def refuse(self, key: MessageKey, reason: str) -> bool:
        row = self.rows.get(key)
        if row is None or row.status is not MessageStatus.QUEUED:
            return False
        self.rows[key] = row.model_copy(
            update={"failure_reason": reason, "status": MessageStatus.FAILED}
        )
        return True

    async def apply_delivery(self, key: MessageKey, update: DeliveryUpdate) -> MessageRow | None:
        row = self.rows.get(key)
        if row is None or not admits(row.status, update.status):
            return None

        changes: dict[str, object] = {
            "provider_message_id": row.provider_message_id or update.provider_message_id,
            "sent_at": row.sent_at or update.at,
            "status": update.status,
        }
        if update.status is MessageStatus.DELIVERED:
            changes["delivered_at"] = update.at
        if update.status is MessageStatus.FAILED:
            changes["failure_reason"] = update.event_type

        self.rows[key] = row.model_copy(update=changes)
        return self.rows[key]

    async def count_send(self, account_id: str, day: date) -> int:
        self.counts[(account_id, day)] += 1
        return self.counts[(account_id, day)]

    async def sends_on(self, account_id: str, day: date) -> int:
        return self.counts[(account_id, day)]

    async def history_page(
        self, account_id: str, month: str, window: HistoryWindow, start: str | None, limit: int
    ) -> tuple[list[MessageRow], str | None]:
        pk = message_partition(account_id, month)
        candidates = sorted(
            (
                (key.sk, row)
                for key, row in self.rows.items()
                if key.pk == pk
                and window.since <= key.sk <= window.until
                and (start is None or key.sk < start)
                and matches(window, row)
            ),
            key=itemgetter(0),
            reverse=True,
        )
        page = [row for _, row in candidates[:limit]]
        if len(candidates) <= limit:
            return page, None
        return page, candidates[limit - 1][0]

    async def conversation_page(
        self, account_id: str, peer: E164, cursor: str | None, limit: int
    ) -> tuple[list[MessageRow], str | None]:
        candidates = sorted(
            (
                row
                for row in self.rows.values()
                if row.account_id == account_id and peer in (row.to, row.from_)
            ),
            key=attrgetter("queued_at"),
            reverse=True,
        )
        if cursor is not None:
            candidates = list(dropwhile(lambda row: row.message_id != cursor, candidates))[1:]

        page = candidates[:limit]
        more = len(candidates) > limit
        return page, page[-1].message_id if more else None

    async def put_template(self, account_id: str, template: Template) -> bool:
        slot = (account_id, template.template_id)
        if slot in self.templates:
            return False
        self.templates[slot] = template
        return True

    async def list_templates(self, account_id: str) -> list[Template]:
        return [template for (owner, _), template in self.templates.items() if owner == account_id]

    async def edit_template(
        self, account_id: str, template_id: str, name: str, body: str
    ) -> Template | None:
        slot = (account_id, template_id)
        existing = self.templates.get(slot)
        if existing is None:
            return None
        self.templates[slot] = existing.model_copy(update={"body": body, "name": name})
        return self.templates[slot]

    async def delete_template(self, account_id: str, template_id: str) -> bool:
        return self.templates.pop((account_id, template_id), None) is not None


def build_service(
    repo: InMemoryMessagingRepo,
    gateway: RecordingGateway,
    *,
    daily_cap: int = DAILY_CAP,
    media: MediaStorage | None = None,
    opt_outs: OptOutSet | None = None,
) -> MessagingService:
    return MessagingService(
        clock=clock_at(NOW),
        gateway=gateway,
        media=media if media is not None else FakeMediaStorage(),
        mode=MODE,
        opt_outs=opt_outs,
        policy=policy(daily_cap=daily_cap),
        repo=repo,
        rng=Random(7),
    )

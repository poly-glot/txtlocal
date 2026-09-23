import csv
import io
import secrets
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from random import Random
from typing import TYPE_CHECKING, Protocol, TypedDict

from txtlocal.shared import telemetry
from txtlocal.shared.errors import BadRequest, Internal, NotFound, RateLimited
from txtlocal.shared.money import Micro
from txtlocal.shared.phone import E164, country_of, normalise
from txtlocal.shared.table import sort_ts
from txtlocal.slices.billing.model import Page
from txtlocal.slices.identity.model import MessagingSettings, UnicodeMode
from txtlocal.slices.messaging.gateway import (
    DEFAULT_MEDIA_SITE,
    MEDIA_EXTENSIONS,
    Dispatch,
    LocalMediaStorage,
    MediaDispatch,
    MediaFile,
    MediaStorage,
    Receipt,
    SmsGateway,
)
from txtlocal.slices.messaging.model import (
    KEY_SEPARATOR,
    MESSAGE_KEY,
    BodyQuote,
    DeliveryStatus,
    DeliveryUpdate,
    Direction,
    Dispatched,
    DispatchOutcome,
    HistoryPage,
    HistoryQuery,
    InboundMessage,
    MediaUploadResponse,
    MessageKey,
    MessageRef,
    MessageRow,
    MessageStatus,
    Product,
    ProviderEvent,
    RefusalReason,
    SendJob,
    Template,
    TemplateRequest,
    Transition,
    message_key_for,
    uuid7_at,
)
from txtlocal.slices.messaging.policy import SendPolicy, is_over_daily_cap
from txtlocal.slices.messaging.repo import HistoryWindow, MessagingRepo
from txtlocal.slices.messaging.segments import (
    MAX_PARTS_CEILING,
    Encoding,
    encoding_of,
    first_non_gsm,
    segments_of,
    units_of,
)

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock

MESSAGE_ACCEPTED = "message_accepted"
DELIVERY_EVENT = "delivery_event"
SPEND_LIMIT = "SPEND_LIMIT"
STALE_CLAIM = timedelta(seconds=60)
RETENTION_DAYS = 120
DEFAULT_RANGE_DAYS = 7
MAX_HISTORY_MONTHS = 5
PAGE_SIZE = 20
EXPORT_MAX_ROWS = 10_000
EXPORT_BATCH = 500
MAX_EXPORT_BATCHES = 1_000
EXPORT_COLUMNS = ("username", "date", "from", "to", "status", "body")
EXPORT_TRUNCATED = f"# truncated at {EXPORT_MAX_ROWS} rows"
EXPORT_UNBOUNDED = "the export read more batches than its cap"
HISTORY_TOO_FAR_BACK = "History covers the last 4 months"
RANGE_INVERTED = "The start date must be on or before the end date"
INVALID_CURSOR = "That page is no longer available"
TEMPLATE_NOT_FOUND = "Template not found"
TEMPLATE_ID_COLLIDED = "a fresh template id already existed"
MESSAGE_NOT_FOUND = "Message not found"
MAX_PARTS_MESSAGE = "Message needs {parts} parts; your limit is {limit}"
GSM_ONLY_MESSAGE = 'Character "{char}" is not available in GSM mode'
MMS_MAX_CHARS = 1_500
MMS_TOO_LONG_MESSAGE = "MMS content is limited to {limit} characters"
MAX_MEDIA_BYTES = 1_048_576
MEDIA_NOT_FOUND = "Media not found"
MEDIA_TOO_LARGE_MESSAGE = "Media is limited to 1 MB"
MEDIA_TYPE_MESSAGE = "Accepted media is image/jpeg, image/png or image/gif"
MMS_JOB_MISSING_MEDIA = "an MMS send job is missing its media key"
DEFAULT_MEDIA_DIR = Path(".local/media")
EVENT_CHANNELS = frozenset({"MEDIA", "TEXT"})
EVENT_STATUS: Mapping[str, DeliveryStatus] = {
    "BLOCKED": MessageStatus.FAILED,
    "CARRIER_BLOCKED": MessageStatus.FAILED,
    "CARRIER_UNREACHABLE": MessageStatus.FAILED,
    "DELIVERED": MessageStatus.DELIVERED,
    "FILE_INACCESSIBLE": MessageStatus.FAILED,
    "FILE_SIZE_EXCEEDED": MessageStatus.FAILED,
    "FILE_TYPE_UNSUPPORTED": MessageStatus.FAILED,
    "INVALID": MessageStatus.FAILED,
    "INVALID_MESSAGE": MessageStatus.FAILED,
    "PENDING": MessageStatus.SENT,
    "PROTECT_BLOCKED": MessageStatus.FAILED,
    "QUEUED": MessageStatus.SENT,
    "SENT": MessageStatus.SENT,
    "SPAM": MessageStatus.FAILED,
    "SUCCESSFUL": MessageStatus.DELIVERED,
    "TTL_EXPIRED": MessageStatus.FAILED,
    "UNKNOWN": MessageStatus.FAILED,
    "UNREACHABLE": MessageStatus.FAILED,
}


class OptOuts(Protocol):
    async def is_opted_out(self, account_id: str, destination: E164) -> bool: ...


class MessageAccepted(TypedDict):
    account_id: str
    campaign_id: str
    country: str
    encoding: Encoding
    message_id: str
    mode: str
    parts: int
    price_micro: int
    product: Product
    sender_id: str
    sender_kind: str
    user_id: str


@dataclass(frozen=True, slots=True)
class HistoryCursor:
    month: str
    start: str | None


def quote_body(body: str, settings: MessagingSettings) -> BodyQuote:
    encoding = encoding_of(body)
    if settings.unicode_mode is UnicodeMode.GSM_ONLY and encoding is Encoding.UCS2:
        raise BadRequest(GSM_ONLY_MESSAGE.format(char=first_non_gsm(body)))

    parts = segments_of(body, encoding)
    limit = min(settings.max_parts, MAX_PARTS_CEILING)
    if parts > limit:
        raise BadRequest(MAX_PARTS_MESSAGE.format(limit=limit, parts=parts))

    return BodyQuote(chars=units_of(body, encoding), encoding=encoding, parts=parts)


def quote_mms_body(body: str) -> BodyQuote:
    encoding = encoding_of(body)
    chars = units_of(body, encoding)
    if chars > MMS_MAX_CHARS:
        raise BadRequest(MMS_TOO_LONG_MESSAGE.format(limit=MMS_MAX_CHARS))

    return BodyQuote(chars=chars, encoding=encoding, parts=1)


def status_of_event(event_type: str) -> DeliveryStatus | None:
    channel, _, outcome = event_type.partition("_")
    if channel not in EVENT_CHANNELS:
        return None
    return EVENT_STATUS.get(outcome)


def is_stale_claim(row: MessageRow, now: datetime) -> bool:
    if row.attempted_at is not None:
        return False
    return row.status is MessageStatus.QUEUED and now - row.queued_at >= STALE_CLAIM


def queued_row(job: SendJob, message_id: str, now: datetime) -> MessageRow:
    return MessageRow(
        account_id=job.account_id,
        body=job.body,
        campaign_id=job.campaign_id,
        country=job.country,
        direction=Direction.OUT,
        encoding=job.encoding,
        from_=job.sender_value,
        kind=job.product,
        media_key=job.media_key,
        message_id=message_id,
        parts=job.parts,
        price_micro=Micro(job.price_micro),
        queued_at=now,
        sender_id=job.sender_id,
        status=MessageStatus.QUEUED,
        subject=job.subject or None,
        to=E164(job.to),
        user_id=job.user_id,
        username=job.username,
    )


def inbound_row(inbound: InboundMessage, account_id: str, message_id: str) -> MessageRow:
    encoding = encoding_of(inbound.body)
    return MessageRow(
        account_id=account_id,
        body=inbound.body,
        campaign_id="",
        country=country_of(inbound.peer),
        direction=Direction.IN,
        encoding=encoding,
        from_=inbound.peer,
        kind=Product.SMS,
        message_id=message_id,
        parts=segments_of(inbound.body, encoding),
        price_micro=Micro(0),
        queued_at=inbound.received_at,
        status=MessageStatus.RECEIVED,
        to=inbound.destination,
        user_id="",
        username="",
    )


def dispatch_of(job: SendJob, key: MessageKey, max_price_usd: str) -> Dispatch:
    return Dispatch(
        body=job.body,
        destination=E164(job.to),
        max_price_usd=max_price_usd,
        message_key=str(key),
        message_type=job.message_type,
        origination=job.origination,
        ttl_seconds=job.ttl_seconds,
    )


def media_dispatch_of(
    job: SendJob, key: MessageKey, max_price_usd: str, media_url: str
) -> MediaDispatch:
    return MediaDispatch(
        body=job.body,
        destination=E164(job.to),
        max_price_usd=max_price_usd,
        media_urls=(media_url,),
        message_key=str(key),
        message_type=job.message_type,
        origination=job.origination,
        subject=job.subject,
        ttl_seconds=job.ttl_seconds,
    )


def message_accepted_fields(job: SendJob, message_id: str, mode: str) -> MessageAccepted:
    return MessageAccepted(
        account_id=job.account_id,
        campaign_id=job.campaign_id,
        country=job.country,
        encoding=job.encoding,
        message_id=message_id,
        mode=mode,
        parts=job.parts,
        price_micro=job.price_micro,
        product=job.product,
        sender_id=job.sender_id,
        sender_kind=job.sender_kind,
        user_id=job.user_id,
    )


def day_of(now: datetime) -> date:
    return now.astimezone(UTC).date()


def sk_bound(day: date) -> str:
    return sort_ts(datetime(day.year, day.month, day.day, tzinfo=UTC))


def months_between(since: date, until: date) -> tuple[str, ...]:
    months: list[str] = []
    year, month = until.year, until.month
    for _ in range(MAX_HISTORY_MONTHS):
        if (year, month) < (since.year, since.month):
            break
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year, month - 1) if month > 1 else (year - 1, 12)
    return tuple(months)


def history_window(query: HistoryQuery, now: datetime) -> HistoryWindow:
    today = day_of(now)
    until = min(query.until or today, today)
    since = query.since or until - timedelta(days=DEFAULT_RANGE_DAYS)
    if since > until:
        raise BadRequest(RANGE_INVERTED)
    if since < today - timedelta(days=RETENTION_DAYS):
        raise BadRequest(HISTORY_TOO_FAR_BACK)

    return HistoryWindow(
        field=query.field,
        kind=query.kind,
        months=months_between(since, until),
        number=normalise(query.q) if query.q else None,
        since=sk_bound(since),
        until=sk_bound(until + timedelta(days=1)),
    )


def encode_cursor(cursor: HistoryCursor) -> str:
    text = f"{cursor.month}{KEY_SEPARATOR}{cursor.start or ''}"
    return urlsafe_b64encode(text.encode()).decode()


def decode_cursor(text: str) -> HistoryCursor:
    try:
        month, separator, start = urlsafe_b64decode(text.encode()).decode().partition(KEY_SEPARATOR)
    except (UnicodeDecodeError, ValueError) as error:
        raise BadRequest(INVALID_CURSOR) from error
    if not (separator and month):
        raise BadRequest(INVALID_CURSOR)
    return HistoryCursor(month=month, start=start or None)


def csv_line(values: Sequence[object]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerow(values)
    return buffer.getvalue()


def export_row(row: MessageRow) -> tuple[object, ...]:
    return (row.username, row.queued_at.isoformat(), row.from_, row.to, row.status, row.body)


def default_media_storage() -> MediaStorage:
    return LocalMediaStorage(directory=DEFAULT_MEDIA_DIR, site=DEFAULT_MEDIA_SITE)


@dataclass(frozen=True, slots=True)
class MessagingService:
    clock: Clock
    gateway: SmsGateway
    mode: str
    policy: SendPolicy
    repo: MessagingRepo
    media: MediaStorage = field(default_factory=default_media_storage)
    opt_outs: OptOuts | None = None
    rng: Random = field(default_factory=secrets.SystemRandom)

    def quote(self, body: str, settings: MessagingSettings) -> BodyQuote:
        return quote_body(body, settings)

    def quote_mms(self, body: str) -> BodyQuote:
        return quote_mms_body(body)

    async def sends_today(self, account_id: str, now: datetime) -> int:
        return await self.repo.sends_on(account_id, day_of(now))

    async def create_media_upload(self, content_type: str) -> MediaUploadResponse:
        if content_type not in MEDIA_EXTENSIONS:
            raise BadRequest(MEDIA_TYPE_MESSAGE)
        upload = await self.media.upload_url(content_type)
        return MediaUploadResponse(key=upload.key, upload_url=upload.upload_url)

    async def store_media(self, key: str, content_type: str, body: bytes) -> None:
        if content_type not in MEDIA_EXTENSIONS:
            raise BadRequest(MEDIA_TYPE_MESSAGE)
        if len(body) > MAX_MEDIA_BYTES:
            raise BadRequest(MEDIA_TOO_LARGE_MESSAGE)
        await self.media.store(key, content_type, body)

    async def read_media(self, key: str) -> MediaFile:
        file = await self.media.read(key)
        if file is None:
            raise NotFound(MEDIA_NOT_FOUND)
        return file

    async def dispatch(self, job: SendJob, now: datetime) -> Dispatched:
        row = queued_row(job, str(uuid7_at(now, self.rng)), now)
        if not await self.repo.claim(row):
            existing = await self._claimed_row(job)
            if existing is None or not is_stale_claim(existing, now):
                return Dispatched(
                    message_id=(existing or row).message_id, outcome=DispatchOutcome.DUPLICATE
                )
            row = existing

        refusal = await self._refusal_at_dispatch(job, now)
        if refusal is not None:
            return await self._refused(row, refusal)

        if not await self.repo.claim_attempt(row.key, now):
            return Dispatched(message_id=row.message_id, outcome=DispatchOutcome.DUPLICATE)

        try:
            receipt = await self._send(job, row.key)
        except BadRequest as refused:
            return await self._refused(row, str(refused))
        except RateLimited:
            return await self._refused(row, SPEND_LIMIT)

        await self.repo.mark_sent(row.key, receipt.provider_message_id, receipt.accepted_at)
        telemetry.log(MESSAGE_ACCEPTED, **message_accepted_fields(job, row.message_id, self.mode))
        return Dispatched(message_id=row.message_id, outcome=DispatchOutcome.ACCEPTED)

    async def apply_event(self, event: ProviderEvent, now: datetime) -> Transition | None:
        key = MessageKey.parse(event.context.get(MESSAGE_KEY, ""))
        if key is None:
            telemetry.log(DELIVERY_EVENT, event_type=event.event_type, outcome="unattributed")
            return None

        status = status_of_event(event.event_type)
        if status is None:
            telemetry.log(DELIVERY_EVENT, event_type=event.event_type, outcome="unmapped")
            return None

        update = DeliveryUpdate(
            at=now,
            event_type=event.event_type,
            provider_message_id=event.message_id,
            status=status,
        )
        row = await self.repo.apply_delivery(key, update)
        if row is None:
            return None

        return Transition(
            account_id=row.account_id,
            campaign_id=row.campaign_id,
            failure_reason=row.failure_reason,
            message_id=row.message_id,
            status=status,
        )

    async def record_inbound(self, account_id: str, inbound: InboundMessage, now: datetime) -> bool:
        row = inbound_row(inbound, account_id, str(uuid7_at(inbound.received_at, self.rng)))
        return await self.repo.record_inbound(row, inbound.inbound_message_id, now)

    async def find_by_provider_id(self, provider_message_id: str) -> MessageRef | None:
        row = await self.repo.find_by_provider_id(provider_message_id)
        if row is None:
            return None
        return MessageRef(
            account_id=row.account_id,
            campaign_id=row.campaign_id,
            message_id=row.message_id,
            peer=row.to,
            sender_id=row.sender_id,
        )

    async def history(self, account_id: str, query: HistoryQuery, now: datetime) -> HistoryPage:
        window = history_window(query, now)
        cursor = decode_cursor(query.cursor) if query.cursor else None

        rows, next_cursor = await self._page(account_id, window, cursor, PAGE_SIZE)
        return HistoryPage(
            cursor=encode_cursor(next_cursor) if next_cursor is not None else None, items=rows
        )

    async def detail(self, account_id: str, message_id: str) -> MessageRow:
        try:
            key = message_key_for(account_id, message_id)
        except ValueError as error:
            raise NotFound(MESSAGE_NOT_FOUND) from error

        row = await self.repo.get(key)
        if row is None:
            raise NotFound(MESSAGE_NOT_FOUND)
        return row

    async def conversation_messages(
        self, account_id: str, peer: E164, cursor: str | None
    ) -> Page[MessageRow]:
        rows, next_cursor = await self.repo.conversation_page(account_id, peer, cursor, PAGE_SIZE)
        return Page[MessageRow](items=rows, next_cursor=next_cursor)

    async def export(
        self, account_id: str, query: HistoryQuery, now: datetime
    ) -> AsyncIterator[str]:
        window = history_window(query, now)
        yield csv_line(EXPORT_COLUMNS)

        emitted = 0
        cursor: HistoryCursor | None = None
        for _ in range(MAX_EXPORT_BATCHES):
            wanted = min(EXPORT_BATCH, EXPORT_MAX_ROWS + 1 - emitted)
            rows, cursor = await self._page(account_id, window, cursor, wanted)
            for row in rows[: EXPORT_MAX_ROWS - emitted]:
                yield csv_line(export_row(row))
            emitted += len(rows)

            if emitted > EXPORT_MAX_ROWS:
                yield f"{EXPORT_TRUNCATED}\n"
                return
            if cursor is None:
                return

        raise Internal(EXPORT_UNBOUNDED)

    async def create_template(
        self, account_id: str, request: TemplateRequest, now: datetime
    ) -> Template:
        template = Template(
            body=request.body,
            created_at=now,
            name=request.name,
            template_id=str(uuid7_at(now, self.rng)),
        )
        if not await self.repo.put_template(account_id, template):
            raise Internal(TEMPLATE_ID_COLLIDED)
        return template

    async def list_templates(self, account_id: str) -> list[Template]:
        return await self.repo.list_templates(account_id)

    async def update_template(
        self, account_id: str, template_id: str, request: TemplateRequest
    ) -> Template:
        template = await self.repo.edit_template(
            account_id, template_id, request.name, request.body
        )
        if template is None:
            raise NotFound(TEMPLATE_NOT_FOUND)
        return template

    async def delete_template(self, account_id: str, template_id: str) -> None:
        if not await self.repo.delete_template(account_id, template_id):
            raise NotFound(TEMPLATE_NOT_FOUND)

    async def _claimed_row(self, job: SendJob) -> MessageRow | None:
        key = await self.repo.find_claim(job.account_id, job.campaign_id, E164(job.to))
        if key is None:
            return None
        return await self.repo.get(key)

    async def _send(self, job: SendJob, key: MessageKey) -> Receipt:
        if job.product is not Product.MMS:
            return await self.gateway.send_text(dispatch_of(job, key, self.policy.max_price_usd))

        if job.media_key is None:
            raise Internal(MMS_JOB_MISSING_MEDIA)

        media_url = self.media.public_url(job.media_key)
        dispatch = media_dispatch_of(job, key, self.policy.max_price_usd, media_url)
        return await self.gateway.send_media(dispatch)

    async def _refusal_at_dispatch(self, job: SendJob, now: datetime) -> str | None:
        if self.opt_outs is not None and await self.opt_outs.is_opted_out(
            job.account_id, E164(job.to)
        ):
            return RefusalReason.OPTED_OUT

        counted = await self.repo.count_send(job.account_id, day_of(now))
        if is_over_daily_cap(counted, self.policy.daily_cap):
            return RefusalReason.DAILY_CAP

        return None

    async def _refused(self, row: MessageRow, reason: str) -> Dispatched:
        if not await self.repo.refuse(row.key, reason):
            return Dispatched(message_id=row.message_id, outcome=DispatchOutcome.DUPLICATE)
        return Dispatched(
            failure_reason=reason, message_id=row.message_id, outcome=DispatchOutcome.REFUSED
        )

    async def _page(
        self, account_id: str, window: HistoryWindow, cursor: HistoryCursor | None, limit: int
    ) -> tuple[list[MessageRow], HistoryCursor | None]:
        rows: list[MessageRow] = []
        months = (
            window.months
            if cursor is None
            else tuple(month for month in window.months if month <= cursor.month)
        )

        for month in months:
            if len(rows) >= limit:
                return rows, HistoryCursor(month=month, start=None)

            start = cursor.start if cursor is not None and month == cursor.month else None
            page, last = await self.repo.history_page(
                account_id, month, window, start, limit - len(rows)
            )
            rows.extend(page)
            if last is not None:
                return rows, HistoryCursor(month=month, start=last)

        return rows, None

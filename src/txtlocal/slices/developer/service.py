import asyncio
import itertools
import re
import uuid
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol, assert_never

from txtlocal.shared.errors import (
    BadRequest,
    Forbidden,
    GatewayTimeout,
    Internal,
    NotFound,
    PaymentRequired,
)
from txtlocal.shared.money import Micro, format_decimal
from txtlocal.shared.phone import E164, country_of, normalise
from txtlocal.shared.table import backoff
from txtlocal.slices.campaigns.model import CampaignDraft
from txtlocal.slices.contacts.model import (
    Contact,
    ContactInput,
    ContactList,
    ContactPage,
    ListRequest,
)
from txtlocal.slices.contacts.service import LIST_NOT_FOUND
from txtlocal.slices.developer.model import (
    MAX_CONTACTS_BATCH,
    MAX_CUSTOM_STRING,
    MAX_LIMIT,
    MAX_MESSAGES,
    MAX_MMS_BODY,
    MAX_SUBJECT,
    MIN_LIMIT,
    MIN_MESSAGES,
    DeveloperGeneral,
    LogFilters,
    LogRow,
    LogsPage,
    LogTiles,
    V3Account,
    V3Balance,
    V3Contact,
    V3ContactCreated,
    V3ContactInput,
    V3ContactPage,
    V3HistoryMessage,
    V3HistoryPage,
    V3HistoryQuery,
    V3List,
    V3ListRequest,
    V3MmsMessage,
    V3MmsSendRequest,
    V3SenderId,
    V3SenderIdsResponse,
    V3SendMessage,
    V3SendRequest,
    V3SendResponse,
    V3SentMessage,
    V3Template,
    V3TemplatesResponse,
)
from txtlocal.slices.developer.repo import IdempotencyRecord, LogRows
from txtlocal.slices.messaging.model import (
    BodyQuote,
    Dispatched,
    DispatchOutcome,
    HistoryPage,
    HistoryQuery,
    MessageRow,
    MessageStatus,
    MessageType,
    Product,
    RefusalReason,
    SendJob,
    Template,
)
from txtlocal.slices.messaging.policy import AccountState, Allowed, Refused, SendPolicy
from txtlocal.slices.messaging.segments import Encoding, encoding_of, units_of
from txtlocal.slices.senders.model import Sender, SenderKind, SenderView, display_of

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock
    from txtlocal.slices.campaigns.model import Campaign
    from txtlocal.slices.developer.repo import DeveloperRepo, LogQueries, LogWindow
    from txtlocal.slices.identity.model import Account, MessagingSettings, Principal
    from txtlocal.slices.messaging.gateway import SmsGateway

CURRENCY = "GBP"
DEFAULT_LOG_WINDOW = timedelta(hours=24)
DISPATCH_CONCURRENCY = 2
LOG_QUERY_DEADLINE = timedelta(seconds=20)
MAX_HISTORY_FETCHES = 10
MAX_LOG_WINDOW = timedelta(days=7)
NO_TRIAL = datetime.min.replace(tzinfo=UTC)
SCHEDULE_MAX_AHEAD = timedelta(days=90)

API_CAMPAIGN_NAME = "API sends"
API_CAMPAIGN_POINTER_MISSING = "api campaign pointer missing after a lost race"

CUSTOM_STRING_MESSAGE = "must be at most 100 characters"
E164_MESSAGE = "must be an E.164 number"
EMPTY_BODY_MESSAGE = "must not be empty"
LOG_FILTER_INVALID_MESSAGE = "That log filter is not valid"
LOG_OUTCOMES = frozenset({"failed", "ok", "refused"})
LOG_QUERY_TIMEOUT_MESSAGE = "The log search took too long, try a narrower range"
LOG_RANGE_INVERTED_MESSAGE = "from must be on or before to"
LOG_RANGE_TOO_WIDE_MESSAGE = "the date range covers at most 7 days"
MEDIA_URL_MESSAGE = "must be an https URL"
MESSAGES_COUNT_MESSAGE = f"messages must have {MIN_MESSAGES} to {MAX_MESSAGES} entries"
MMS_BODY_MESSAGE = f"must be 1 to {MAX_MMS_BODY} characters"
CONTACTS_COUNT_MESSAGE = f"contacts must have 1 to {MAX_CONTACTS_BATCH} entries"
NO_CONTACT_MESSAGE = "No contact with that id"
NO_LIST_MESSAGE = "No list with that id"
NO_MESSAGE_MESSAGE = "No message with that id"
SCHEDULE_RANGE_MESSAGE = "must be in the future and at most 90 days out"
SCHEDULE_UNSUPPORTED_MESSAGE = "scheduling is not available yet; omit schedule to send now"
SUBJECT_MESSAGE = f"must be at most {MAX_SUBJECT} characters"


class AccountLookup(Protocol):
    async def account_of(self, account_id: str) -> Account: ...


class BalanceView(Protocol):
    @property
    def balance_micro(self) -> int: ...

    @property
    def has_topped_up(self) -> bool: ...

    @property
    def trial_ends_at(self) -> datetime | None: ...


class Billing(Protocol):
    async def balance(self, account_id: str, now: datetime) -> BalanceView: ...

    async def rate(self, country: str, product: Product) -> Micro: ...

    async def reserve(
        self, account_id: str, amount_micro: Micro, ref: str, now: datetime
    ) -> None: ...

    async def settle(
        self, account_id: str, ref: str, reserved_micro: Micro, settled_micro: Micro, now: datetime
    ) -> None: ...


class CampaignLanding(Protocol):
    async def create_draft(
        self, principal: Principal, draft: CampaignDraft, now: datetime
    ) -> Campaign: ...


class Contacts(Protocol):
    async def add_contact(
        self, account_id: str, list_id: str, request: ContactInput
    ) -> Contact: ...

    async def contacts(
        self, account_id: str, list_id: str, q: str | None, cursor: str | None, limit: int
    ) -> ContactPage: ...

    async def create_list(self, account_id: str, request: ListRequest) -> ContactList: ...

    async def lists(self, account_id: str, q: str | None) -> list[ContactList]: ...

    async def opt_outs(self, account_id: str) -> frozenset[E164]: ...

    async def remove_contact(self, account_id: str, list_id: str, contact_id: str) -> None: ...


class Messaging(Protocol):
    async def detail(self, account_id: str, message_id: str) -> MessageRow: ...

    async def dispatch(self, job: SendJob, now: datetime) -> Dispatched: ...

    async def history(self, account_id: str, query: HistoryQuery, now: datetime) -> HistoryPage: ...

    async def list_templates(self, account_id: str) -> list[Template]: ...

    def quote(self, body: str, settings: MessagingSettings) -> BodyQuote: ...

    async def sends_today(self, account_id: str, now: datetime) -> int: ...


class Senders(Protocol):
    async def resolve(self, account_id: str, sender_id: str | None, country: str) -> Sender: ...

    async def senders(self, account_id: str) -> list[Sender]: ...

    async def verified_numbers(self, account_id: str) -> frozenset[E164]: ...


class Settings(Protocol):
    async def messaging_settings(self, account_id: str) -> MessagingSettings: ...


def field_error(index: int, field_name: str, message: str) -> BadRequest:
    return BadRequest(f"messages[{index}].{field_name}: {message}")


def policy_refusal(reason: RefusalReason, message: str) -> Forbidden | PaymentRequired:
    if reason is RefusalReason.INSUFFICIENT_BALANCE:
        return PaymentRequired(message)

    refused = Forbidden(message)
    refused.code = reason
    return refused


@dataclass(frozen=True, slots=True)
class CheckedMessage:
    body: str
    custom_string: str | None
    schedule: datetime | None
    sender_id: str | None
    to: E164


def checked_to(index: int, raw: str, default_country: str) -> E164:
    try:
        return normalise(raw, default_country)
    except BadRequest as error:
        raise field_error(index, "to", E164_MESSAGE) from error


def checked_custom_string(index: int, custom_string: str | None) -> None:
    if custom_string is not None and len(custom_string) > MAX_CUSTOM_STRING:
        raise field_error(index, "customString", CUSTOM_STRING_MESSAGE)


def checked_schedule(index: int, schedule: datetime | None, now: datetime) -> None:
    if schedule is None:
        return
    if schedule <= now or schedule > now + SCHEDULE_MAX_AHEAD:
        raise field_error(index, "schedule", SCHEDULE_RANGE_MESSAGE)
    raise field_error(index, "schedule", SCHEDULE_UNSUPPORTED_MESSAGE)


def checked_send_message(
    index: int, message: V3SendMessage, default_country: str, now: datetime
) -> CheckedMessage:
    to = checked_to(index, message.to, default_country)
    if not message.body:
        raise field_error(index, "body", EMPTY_BODY_MESSAGE)
    checked_custom_string(index, message.custom_string)
    checked_schedule(index, message.schedule, now)

    return CheckedMessage(
        body=message.body,
        custom_string=message.custom_string,
        schedule=message.schedule,
        sender_id=message.from_,
        to=to,
    )


def checked_mms_message(
    index: int, message: V3MmsMessage, default_country: str, now: datetime
) -> CheckedMessage:
    to = checked_to(index, message.to, default_country)
    if not 1 <= len(message.body) <= MAX_MMS_BODY:
        raise field_error(index, "body", MMS_BODY_MESSAGE)
    if message.subject is not None and len(message.subject) > MAX_SUBJECT:
        raise field_error(index, "subject", SUBJECT_MESSAGE)
    if not message.media_url.startswith("https://"):
        raise field_error(index, "mediaUrl", MEDIA_URL_MESSAGE)
    checked_custom_string(index, message.custom_string)
    checked_schedule(index, message.schedule, now)

    return CheckedMessage(
        body=message.body,
        custom_string=message.custom_string,
        schedule=message.schedule,
        sender_id=message.from_,
        to=to,
    )


def checked_message_count(count: int) -> None:
    if not MIN_MESSAGES <= count <= MAX_MESSAGES:
        raise BadRequest(MESSAGES_COUNT_MESSAGE)


def mms_quote(body: str) -> BodyQuote:
    encoding = encoding_of(body)
    return BodyQuote(chars=units_of(body, encoding), encoding=encoding, parts=1)


def billing_product_of(product: Product) -> Product:
    return Product.SMS if product is Product.MMS_AS_LINK else product


@dataclass(frozen=True, slots=True)
class PricedMessage:
    body: str
    country: str
    custom_string: str | None
    encoding: Encoding
    parts: int
    price_micro: Micro
    product: Product
    sender: Sender
    to: E164


def origination_of(sender: Sender) -> str:
    return sender.provider_identity or sender.value


def job_of(
    principal: Principal, campaign_id: str, message: PricedMessage, message_type: MessageType
) -> SendJob:
    return SendJob(
        account_id=principal.account_id,
        body=message.body,
        campaign_id=campaign_id,
        country=message.country,
        encoding=message.encoding,
        message_type=message_type,
        origination=origination_of(message.sender),
        parts=message.parts,
        price_micro=message.price_micro,
        product=message.product,
        sender_id=message.sender.sender_id,
        sender_kind=message.sender.kind,
        sender_value=message.sender.value,
        to=message.to,
        user_id=principal.user_id,
        username=principal.username,
    )


def sent_message_of(message: PricedMessage, dispatched: Dispatched) -> V3SentMessage:
    refused = dispatched.outcome is DispatchOutcome.REFUSED
    return V3SentMessage(
        body=message.body,
        country=message.country,
        custom_string=message.custom_string,
        encoding=message.encoding,
        from_=message.sender.value,
        message_id=dispatched.message_id,
        parts=message.parts,
        price=format_decimal(Micro(0) if refused else message.price_micro),
        product=message.product,
        schedule=None,
        status=MessageStatus.FAILED if refused else MessageStatus.QUEUED,
        to=message.to,
    )


def v3_history_message_of(row: MessageRow, custom_string: str | None) -> V3HistoryMessage:
    return V3HistoryMessage(
        body=row.body,
        custom_string=custom_string,
        delivered_at=row.delivered_at,
        direction=row.direction,
        failure_reason=row.failure_reason,
        from_=row.from_,
        message_id=row.message_id,
        parts=row.parts,
        price=format_decimal(row.price_micro),
        sent_at=row.sent_at,
        status=row.status,
        to=row.to,
        user_id=row.user_id,
    )


def matches_history_filter(row: MessageRow, query: V3HistoryQuery) -> bool:
    if query.direction is not None and row.direction is not query.direction:
        return False
    return query.status is None or row.status.value == query.status.value


def v3_contact_fields(contact: Contact) -> dict[str, str]:
    return {"cf1": contact.cf1, "cf2": contact.cf2, "cf3": contact.cf3, "cf4": contact.cf4}


def v3_contact_of(contact: Contact) -> V3Contact:
    return V3Contact(
        custom_fields=v3_contact_fields(contact),
        email=contact.email,
        first_name=contact.first_name,
        last_name=contact.last_name,
        mobile=contact.mobile,
    )


def v3_contact_created_of(contact: Contact, *, created: bool) -> V3ContactCreated:
    return V3ContactCreated(
        created=created,
        custom_fields=v3_contact_fields(contact),
        email=contact.email,
        first_name=contact.first_name,
        last_name=contact.last_name,
        mobile=contact.mobile,
    )


def contact_input_of(request: V3ContactInput) -> ContactInput:
    return ContactInput(
        cf1=request.custom_fields.get("cf1", ""),
        cf2=request.custom_fields.get("cf2", ""),
        cf3=request.custom_fields.get("cf3", ""),
        cf4=request.custom_fields.get("cf4", ""),
        email=request.email,
        first_name=request.first_name,
        last_name=request.last_name,
        mobile=request.mobile,
    )


def v3_list_of(contact_list: ContactList) -> V3List:
    return V3List(
        contact_count=contact_list.contact_count,
        is_opt_out=contact_list.kind.value == "OPT_OUT",
        list_id=contact_list.list_id,
        name=contact_list.name,
        updated_at=contact_list.created_at,
    )


def v3_sender_value(sender: Sender) -> str:
    return display_of(sender) if sender.kind is SenderKind.SHARED else sender.value


def v3_sender_of(sender: Sender) -> V3SenderId:
    return V3SenderId(
        countries=[sender.country],
        kind=sender.kind.value,
        sender_id=sender.sender_id,
        status=sender.status.value,
        value=v3_sender_value(sender),
    )


def not_found_as(error: NotFound, *, list_message: str, contact_message: str) -> NotFound:
    return NotFound(list_message if str(error) == LIST_NOT_FOUND else contact_message)


LOG_ROUTE_PATTERN = re.compile(r"^[A-Za-z0-9/_.{}-]{1,200}$")
LOG_USER_ID_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def checked_log_filters(filters: LogFilters) -> LogFilters:
    if filters.outcome is not None and filters.outcome not in LOG_OUTCOMES:
        raise BadRequest(LOG_FILTER_INVALID_MESSAGE)
    if filters.route is not None and not LOG_ROUTE_PATTERN.match(filters.route):
        raise BadRequest(LOG_FILTER_INVALID_MESSAGE)
    if filters.user_id is not None and not LOG_USER_ID_PATTERN.match(filters.user_id):
        raise BadRequest(LOG_FILTER_INVALID_MESSAGE)
    return filters


def checked_log_window(since: datetime | None, until: datetime | None, now: datetime) -> LogWindow:
    end = until or now
    start = since or (now - DEFAULT_LOG_WINDOW)
    if start > end:
        raise BadRequest(LOG_RANGE_INVERTED_MESSAGE)
    if end - start > MAX_LOG_WINDOW:
        raise BadRequest(LOG_RANGE_TOO_WIDE_MESSAGE)
    return start, end


def tiles_of(rows: Sequence[LogRow]) -> LogTiles:
    tally = Counter(row.outcome for row in rows)
    return LogTiles(
        failed=tally.get("refused", 0) + tally.get("failed", 0),
        successful=tally.get("ok", 0),
        total=len(rows),
    )


@dataclass(frozen=True, slots=True)
class DeveloperService:
    accounts: AccountLookup
    base_url: str
    billing: Billing
    campaigns: CampaignLanding
    clock: Clock
    contacts: Contacts
    docs_url: str
    gateway: SmsGateway
    log_queries: LogQueries
    messaging: Messaging
    policy: SendPolicy
    rate_limit_per_minute: int
    repo: DeveloperRepo
    senders: Senders
    settings: Settings

    async def begin_idempotency(self, user_id: str, idempotency_key: str, now: datetime) -> bool:
        return await self.repo.begin_idempotency(user_id, idempotency_key, now)

    async def peek_idempotency(
        self, user_id: str, idempotency_key: str
    ) -> IdempotencyRecord | None:
        return await self.repo.peek_idempotency(user_id, idempotency_key)

    async def finish_idempotency(
        self, user_id: str, idempotency_key: str, status: int, body: str
    ) -> None:
        await self.repo.finish_idempotency(user_id, idempotency_key, status, body)

    async def send(
        self, principal: Principal, request: V3SendRequest, now: datetime
    ) -> V3SendResponse:
        checked_message_count(len(request.messages))
        settings = await self.settings.messaging_settings(principal.account_id)
        checked = [
            checked_send_message(index, message, settings.default_country, now)
            for index, message in enumerate(request.messages)
        ]

        priced = await self._priced_messages(
            principal.account_id,
            checked,
            now,
            quote_of=lambda body: self.messaging.quote(body, settings),
            product_of=lambda _country: Product.SMS,
        )
        return await self._send_priced(principal, priced, now)

    async def send_mms(
        self, principal: Principal, request: V3MmsSendRequest, now: datetime
    ) -> V3SendResponse:
        checked_message_count(len(request.messages))
        settings = await self.settings.messaging_settings(principal.account_id)
        checked = [
            checked_mms_message(index, message, settings.default_country, now)
            for index, message in enumerate(request.messages)
        ]

        mms_countries = self.gateway.capabilities.mms_countries
        priced = await self._priced_messages(
            principal.account_id,
            checked,
            now,
            quote_of=mms_quote,
            product_of=lambda country: (
                Product.MMS if country in mms_countries else Product.MMS_AS_LINK
            ),
        )
        return await self._send_priced(principal, priced, now)

    async def history(
        self, principal: Principal, query: V3HistoryQuery, now: datetime
    ) -> V3HistoryPage:
        limit = min(max(query.limit, MIN_LIMIT), MAX_LIMIT)
        since = query.since.astimezone(UTC).date() if query.since else None
        until = query.until.astimezone(UTC).date() if query.until else None

        collected: list[MessageRow] = []
        cursor = query.cursor
        for _ in range(MAX_HISTORY_FETCHES):
            page = await self.messaging.history(
                principal.account_id, HistoryQuery(cursor=cursor, since=since, until=until), now
            )
            collected.extend(row for row in page.items if matches_history_filter(row, query))
            cursor = page.cursor
            if len(collected) >= limit or cursor is None:
                break

        custom_strings = await self.repo.custom_strings_of([row.message_id for row in collected])
        return V3HistoryPage(
            messages=[
                v3_history_message_of(row, custom_strings.get(row.message_id)) for row in collected
            ],
            next_cursor=cursor,
        )

    async def detail(self, principal: Principal, message_id: str) -> V3HistoryMessage:
        try:
            row = await self.messaging.detail(principal.account_id, message_id)
        except NotFound as error:
            raise NotFound(NO_MESSAGE_MESSAGE) from error

        custom_strings = await self.repo.custom_strings_of([message_id])
        return v3_history_message_of(row, custom_strings.get(message_id))

    async def account(self, principal: Principal, now: datetime) -> V3Account:
        account, balance = await asyncio.gather(
            self.accounts.account_of(principal.account_id),
            self.billing.balance(principal.account_id, now),
        )
        return V3Account(
            account_id=account.account_id,
            balance=format_decimal(Micro(balance.balance_micro)),
            country=account.pricing_country,
            currency=CURRENCY,
            email=account.email,
            name=account.name,
            trial_ends_at=balance.trial_ends_at,
        )

    async def balance(self, principal: Principal, now: datetime) -> V3Balance:
        balance = await self.billing.balance(principal.account_id, now)
        return V3Balance(balance=format_decimal(Micro(balance.balance_micro)), currency=CURRENCY)

    async def lists(self, principal: Principal, q: str | None) -> list[V3List]:
        return [v3_list_of(one) for one in await self.contacts.lists(principal.account_id, q)]

    async def create_list(self, principal: Principal, request: V3ListRequest) -> V3List:
        created = await self.contacts.create_list(
            principal.account_id, ListRequest(name=request.name)
        )
        return v3_list_of(created)

    async def list_contacts(
        self, principal: Principal, list_id: str, cursor: str | None, limit: int
    ) -> V3ContactPage:
        wanted = min(max(limit, MIN_LIMIT), MAX_LIMIT)
        try:
            page = await self.contacts.contacts(principal.account_id, list_id, None, cursor, wanted)
        except NotFound as error:
            raise NotFound(NO_LIST_MESSAGE) from error

        return V3ContactPage(
            contacts=[v3_contact_of(one) for one in page.items], next_cursor=page.cursor
        )

    async def add_contact(
        self, principal: Principal, list_id: str, request: V3ContactInput
    ) -> V3ContactCreated:
        settings = await self.settings.messaging_settings(principal.account_id)
        mobile = normalise(request.mobile, settings.default_country)

        try:
            existing = await self.contacts.contacts(principal.account_id, list_id, mobile, None, 1)
            saved = await self.contacts.add_contact(
                principal.account_id, list_id, contact_input_of(request)
            )
        except NotFound as error:
            raise NotFound(NO_LIST_MESSAGE) from error

        created = not any(one.mobile == mobile for one in existing.items)
        return v3_contact_created_of(saved, created=created)

    async def add_contacts(
        self, principal: Principal, list_id: str, requests: Sequence[V3ContactInput]
    ) -> list[V3ContactCreated]:
        if not 1 <= len(requests) <= MAX_CONTACTS_BATCH:
            raise BadRequest(CONTACTS_COUNT_MESSAGE)

        return [await self.add_contact(principal, list_id, request) for request in requests]

    async def remove_contact(self, principal: Principal, list_id: str, contact_id: str) -> None:
        try:
            await self.contacts.remove_contact(principal.account_id, list_id, contact_id)
        except NotFound as error:
            raise not_found_as(
                error, list_message=NO_LIST_MESSAGE, contact_message=NO_CONTACT_MESSAGE
            ) from error

    async def sender_ids(self, principal: Principal) -> V3SenderIdsResponse:
        senders = await self.senders.senders(principal.account_id)
        return V3SenderIdsResponse(senders=[v3_sender_of(one) for one in senders])

    async def templates(self, principal: Principal) -> V3TemplatesResponse:
        templates = await self.messaging.list_templates(principal.account_id)
        return V3TemplatesResponse(
            templates=[
                V3Template(body=one.body, name=one.name, template_id=one.template_id)
                for one in templates
            ]
        )

    async def general(self) -> DeveloperGeneral:
        return DeveloperGeneral(
            base_url=self.base_url,
            docs_url=self.docs_url,
            rate_limit_per_minute=self.rate_limit_per_minute,
        )

    async def logs(
        self,
        principal: Principal,
        filters: LogFilters,
        since: datetime | None,
        until: datetime | None,
        now: datetime,
    ) -> LogsPage:
        window = checked_log_window(since, until, now)
        query_id = await self.log_queries.start(
            principal.account_id, checked_log_filters(filters), window
        )

        deadline = now + LOG_QUERY_DEADLINE
        attempt = 0
        while self.clock() < deadline:
            result = await self.log_queries.poll(query_id)
            if isinstance(result, LogRows):
                return LogsPage(rows=result.rows, tiles=tiles_of(result.rows))

            await asyncio.sleep(backoff(attempt))
            attempt += 1

        raise GatewayTimeout(LOG_QUERY_TIMEOUT_MESSAGE)

    async def _priced_messages(
        self,
        account_id: str,
        checked: Sequence[CheckedMessage],
        now: datetime,
        quote_of: Callable[[str], BodyQuote],
        product_of: Callable[[str], Product],
    ) -> list[PricedMessage]:
        account_state = await self._account_state(account_id, now)
        rates: dict[tuple[str, Product], Micro] = {}
        senders: dict[tuple[str | None, str], Sender] = {}
        priced: list[PricedMessage] = []

        for index, message in enumerate(checked):
            country = country_of(message.to)
            product = product_of(country)
            sender = await self._cached_sender(
                senders, index, account_id, message.sender_id, country
            )
            quote = quote_of(message.body)
            rate = await self._cached_rate(rates, country, billing_product_of(product))
            price = Micro(rate * max(quote.parts, 1))

            match self.policy.allow(account_state, SenderView.of(sender), message.to, price, now):
                case Refused(message=refusal_message, reason=reason):
                    raise policy_refusal(reason, refusal_message)
                case Allowed():
                    pass
                case _ as unreachable:
                    assert_never(unreachable)

            priced.append(
                PricedMessage(
                    body=message.body,
                    country=country,
                    custom_string=message.custom_string,
                    encoding=quote.encoding,
                    parts=quote.parts,
                    price_micro=price,
                    product=product,
                    sender=sender,
                    to=message.to,
                )
            )

        return priced

    async def _cached_rate(
        self, cache: dict[tuple[str, Product], Micro], country: str, product: Product
    ) -> Micro:
        key = (country, product)
        if key not in cache:
            cache[key] = await self.billing.rate(country, product)
        return cache[key]

    async def _cached_sender(
        self,
        cache: dict[tuple[str | None, str], Sender],
        index: int,
        account_id: str,
        sender_id: str | None,
        country: str,
    ) -> Sender:
        key = (sender_id, country)
        if key not in cache:
            cache[key] = await self._resolved_sender(index, account_id, sender_id, country)
        return cache[key]

    async def _resolved_sender(
        self, index: int, account_id: str, sender_id: str | None, country: str
    ) -> Sender:
        try:
            return await self.senders.resolve(account_id, sender_id, country)
        except (NotFound, BadRequest) as error:
            message = f"not a sender you can use for {country}"
            raise field_error(index, "from", message) from error

    async def _send_priced(
        self, principal: Principal, priced: Sequence[PricedMessage], now: datetime
    ) -> V3SendResponse:
        total = Micro(sum(message.price_micro for message in priced))
        campaign_id = await self._landing_campaign_id(principal, now)
        batch_id = str(uuid.uuid7())

        await self.billing.reserve(principal.account_id, total, batch_id, now)
        dispatched = await self._dispatch_all(principal, campaign_id, priced, now)

        settled = Micro(
            sum(
                Micro(0) if outcome.outcome is DispatchOutcome.REFUSED else message.price_micro
                for message, outcome in zip(priced, dispatched, strict=True)
            )
        )
        if settled != total:
            await self.billing.settle(principal.account_id, batch_id, total, settled, now)

        await self._remember_custom_strings(priced, dispatched)

        return V3SendResponse(
            messages=[sent_message_of(m, d) for m, d in zip(priced, dispatched, strict=True)],
            total_price=format_decimal(settled),
        )

    async def _dispatch_all(
        self,
        principal: Principal,
        campaign_id: str,
        priced: Sequence[PricedMessage],
        now: datetime,
    ) -> list[Dispatched]:
        jobs = [
            job_of(principal, campaign_id, message, MessageType.TRANSACTIONAL) for message in priced
        ]
        dispatched: list[Dispatched] = []
        for batch in itertools.batched(jobs, DISPATCH_CONCURRENCY, strict=False):
            dispatched.extend(
                await asyncio.gather(*(self.messaging.dispatch(job, now) for job in batch))
            )

        return dispatched

    async def _remember_custom_strings(
        self, priced: Sequence[PricedMessage], dispatched: Sequence[Dispatched]
    ) -> None:
        entries = {
            d.message_id: m.custom_string
            for m, d in zip(priced, dispatched, strict=True)
            if m.custom_string is not None
        }
        if entries:
            await self.repo.remember_custom_strings(entries)

    async def _landing_campaign_id(self, principal: Principal, now: datetime) -> str:
        existing = await self.repo.api_campaign_id(principal.account_id)
        if existing is not None:
            return existing

        campaign = await self.campaigns.create_draft(
            principal, CampaignDraft(name=API_CAMPAIGN_NAME), now
        )
        if await self.repo.remember_api_campaign_id(principal.account_id, campaign.campaign_id):
            return campaign.campaign_id

        winner = await self.repo.api_campaign_id(principal.account_id)
        if winner is None:
            raise Internal(API_CAMPAIGN_POINTER_MISSING)
        return winner

    async def _account_state(self, account_id: str, now: datetime) -> AccountState:
        balance, opted_out, sends_today, verified = await asyncio.gather(
            self.billing.balance(account_id, now),
            self.contacts.opt_outs(account_id),
            self.messaging.sends_today(account_id, now),
            self.senders.verified_numbers(account_id),
        )
        return AccountState(
            balance_micro=Micro(balance.balance_micro),
            has_topped_up=balance.has_topped_up,
            opted_out=opted_out,
            sends_today=sends_today,
            trial_ends_at=balance.trial_ends_at or NO_TRIAL,
            verified_numbers=verified,
        )

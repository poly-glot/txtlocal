from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from txtlocal.shared.errors import BadRequest, NotFound
from txtlocal.shared.money import Micro
from txtlocal.shared.phone import E164
from txtlocal.shared.testing import RecordingBus
from txtlocal.slices.campaigns.model import (
    Campaign,
    CampaignCounts,
    CampaignDraft,
    CampaignKind,
    CampaignStatus,
)
from txtlocal.slices.contacts.model import (
    Contact,
    ContactInput,
    ContactList,
    ContactPage,
    ListRequest,
)
from txtlocal.slices.developer.model import IdempotencyStatus, LogFilters
from txtlocal.slices.developer.repo import IdempotencyRecord, LogResult, LogWindow
from txtlocal.slices.identity.model import Account, MessagingSettings, Principal, Role
from txtlocal.slices.messaging.gateway import FakeSmsGateway
from txtlocal.slices.messaging.model import (
    BodyQuote,
    Dispatched,
    DispatchOutcome,
    HistoryPage,
    HistoryQuery,
    MessageRow,
    Product,
    SendJob,
    Template,
)
from txtlocal.slices.messaging.segments import encoding_of, segments_of, units_of

if TYPE_CHECKING:
    from txtlocal.slices.senders.model import Sender

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
ACCOUNT_ID = "acc_dev_fake"
USER_ID = "usr_dev_fake"
PRINCIPAL = Principal(
    account_id=ACCOUNT_ID, role=Role.OWNER, user_id=USER_ID, username="dev@example.com"
)


def clock() -> datetime:
    return NOW


def gateway() -> FakeSmsGateway:
    return FakeSmsGateway(bus=RecordingBus(), clock=clock)


@dataclass(frozen=True, slots=True)
class FakeAccounts:
    account: Account

    async def account_of(self, _account_id: str) -> Account:
        return self.account


@dataclass(frozen=True, slots=True)
class BalanceStub:
    balance_micro: int
    has_topped_up: bool = True
    trial_ends_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class FakeBilling:
    balance_micro: int = 100_000_000
    has_topped_up: bool = True
    rate_micro: Micro = field(default_factory=lambda: Micro(10_000))
    reserved: list[tuple[str, Micro, str]] = field(default_factory=list)
    settled: list[tuple[str, str, Micro, Micro]] = field(default_factory=list)

    async def balance(self, _account_id: str, _now: datetime) -> BalanceStub:
        return BalanceStub(balance_micro=self.balance_micro, has_topped_up=self.has_topped_up)

    async def rate(self, _country: str, _product: Product) -> Micro:
        return self.rate_micro

    async def reserve(self, account_id: str, amount_micro: Micro, ref: str, _now: datetime) -> None:
        self.reserved.append((account_id, amount_micro, ref))

    async def settle(
        self,
        account_id: str,
        ref: str,
        reserved_micro: Micro,
        settled_micro: Micro,
        _now: datetime,
    ) -> None:
        self.settled.append((account_id, ref, reserved_micro, settled_micro))


@dataclass(frozen=True, slots=True)
class FakeCampaigns:
    next_id: str = "cmp_landing_1"
    created: list[CampaignDraft] = field(default_factory=list)

    async def create_draft(
        self, principal: Principal, draft: CampaignDraft, now: datetime
    ) -> Campaign:
        self.created.append(draft)
        return Campaign(
            body=draft.body,
            campaign_id=self.next_id,
            channel=draft.product,
            counts=CampaignCounts(recipients=0),
            created_at=now,
            kind=CampaignKind.LIST,
            name=draft.name,
            quote_micro=Micro(0),
            recipients=[],
            reserved_micro=Micro(0),
            sender_id=draft.sender_id,
            shorten_urls=draft.shorten_urls,
            status=CampaignStatus.DRAFT,
            user_id=principal.user_id,
            username=principal.username,
        )


@dataclass(frozen=True, slots=True)
class FakeContacts:
    opted_out: frozenset[E164] = frozenset()
    lists_by_id: dict[str, ContactList] = field(default_factory=dict)
    contacts_by_list: dict[str, list[Contact]] = field(default_factory=dict)

    async def opt_outs(self, _account_id: str) -> frozenset[E164]:
        return self.opted_out

    async def lists(self, _account_id: str, _q: str | None) -> list[ContactList]:
        return list(self.lists_by_id.values())

    async def create_list(self, _account_id: str, request: ListRequest) -> ContactList:
        created = ContactList(
            created_at=NOW, list_id=f"lst_{len(self.lists_by_id) + 1}", name=request.name
        )
        self.lists_by_id[created.list_id] = created
        return created

    async def contacts(
        self, _account_id: str, list_id: str, q: str | None, _cursor: str | None, limit: int
    ) -> ContactPage:
        if list_id not in self.lists_by_id:
            raise NotFound("List not found")

        items = self.contacts_by_list.get(list_id, [])
        matching = [one for one in items if q is None or one.mobile == q]
        return ContactPage(cursor=None, items=matching[:limit])

    async def add_contact(self, account_id: str, list_id: str, request: ContactInput) -> Contact:
        if list_id not in self.lists_by_id:
            raise NotFound("List not found")

        contact = Contact(
            account_id=account_id,
            cf1=request.cf1,
            cf2=request.cf2,
            cf3=request.cf3,
            cf4=request.cf4,
            email=request.email,
            first_name=request.first_name,
            last_name=request.last_name,
            list_id=list_id,
            mobile=E164(request.mobile),
            updated_at=NOW,
        )
        self.contacts_by_list.setdefault(list_id, []).append(contact)
        return contact

    async def remove_contact(self, _account_id: str, list_id: str, contact_id: str) -> None:
        if list_id not in self.lists_by_id:
            raise NotFound("List not found")

        items = self.contacts_by_list.get(list_id, [])
        remaining = [one for one in items if one.mobile != contact_id]
        if len(remaining) == len(items):
            raise NotFound("Contact not found")
        self.contacts_by_list[list_id] = remaining


@dataclass(frozen=True, slots=True)
class FakeMessaging:
    dispatched: list[SendJob] = field(default_factory=list)
    detail_rows: dict[str, MessageRow] = field(default_factory=dict)
    history_rows: list[MessageRow] = field(default_factory=list)
    refuse: frozenset[str] = frozenset()
    templates: list[Template] = field(default_factory=list)

    def quote(self, body: str, _settings: MessagingSettings) -> BodyQuote:
        encoding = encoding_of(body)
        return BodyQuote(
            chars=units_of(body, encoding), encoding=encoding, parts=segments_of(body, encoding)
        )

    async def sends_today(self, _account_id: str, _now: datetime) -> int:
        return 0

    async def dispatch(self, job: SendJob, _now: datetime) -> Dispatched:
        self.dispatched.append(job)
        message_id = f"msg_dev_fake_{len(self.dispatched)}"
        if job.to in self.refuse:
            return Dispatched(
                failure_reason="OPTED_OUT", message_id=message_id, outcome=DispatchOutcome.REFUSED
            )
        return Dispatched(message_id=message_id, outcome=DispatchOutcome.ACCEPTED)

    async def detail(self, _account_id: str, message_id: str) -> MessageRow:
        row = self.detail_rows.get(message_id)
        if row is None:
            raise NotFound("Message not found")
        return row

    async def history(self, _account_id: str, _query: HistoryQuery, _now: datetime) -> HistoryPage:
        return HistoryPage(cursor=None, items=list(self.history_rows))

    async def list_templates(self, _account_id: str) -> list[Template]:
        return list(self.templates)


@dataclass(frozen=True, slots=True)
class FakeSenders:
    sender: Sender
    always_ready: bool = False
    verified: frozenset[E164] = frozenset()

    async def resolve(self, _account_id: str, _sender_id: str | None, country: str) -> Sender:
        if not self.always_ready and self.sender.country != country:
            raise BadRequest(f"{self.sender.value} is not ready to send to {country}")
        return self.sender

    async def senders(self, _account_id: str) -> list[Sender]:
        return [self.sender]

    async def verified_numbers(self, _account_id: str) -> frozenset[E164]:
        return self.verified


@dataclass(frozen=True, slots=True)
class FakeSettings:
    settings: MessagingSettings = field(default_factory=MessagingSettings)

    async def messaging_settings(self, _account_id: str) -> MessagingSettings:
        return self.settings


@dataclass(frozen=True, slots=True)
class FakeRepo:
    campaign_ids: dict[str, str] = field(default_factory=dict)
    custom_strings: dict[str, str] = field(default_factory=dict)
    idempotency: dict[tuple[str, str], IdempotencyRecord] = field(default_factory=dict)

    async def api_campaign_id(self, account_id: str) -> str | None:
        return self.campaign_ids.get(account_id)

    async def remember_api_campaign_id(self, account_id: str, campaign_id: str) -> bool:
        if account_id in self.campaign_ids:
            return False
        self.campaign_ids[account_id] = campaign_id
        return True

    async def begin_idempotency(self, user_id: str, idempotency_key: str, _now: datetime) -> bool:
        key = (user_id, idempotency_key)
        if key in self.idempotency:
            return False
        self.idempotency[key] = IdempotencyRecord(
            response_body=None, response_status=None, status=IdempotencyStatus.IN_FLIGHT
        )
        return True

    async def peek_idempotency(
        self, user_id: str, idempotency_key: str
    ) -> IdempotencyRecord | None:
        return self.idempotency.get((user_id, idempotency_key))

    async def finish_idempotency(
        self, user_id: str, idempotency_key: str, status: int, body: str
    ) -> None:
        self.idempotency[(user_id, idempotency_key)] = IdempotencyRecord(
            response_body=body, response_status=status, status=IdempotencyStatus.DONE
        )

    async def remember_custom_strings(self, entries: Mapping[str, str]) -> None:
        self.custom_strings.update(entries)

    async def custom_strings_of(self, message_ids: Sequence[str]) -> dict[str, str]:
        return {one: self.custom_strings[one] for one in message_ids if one in self.custom_strings}


@dataclass(frozen=True, slots=True)
class FakeLogQueries:
    result: LogResult

    async def start(self, _account_id: str, _filters: LogFilters, _window: LogWindow) -> str:
        return "query_1"

    async def poll(self, _query_id: str) -> LogResult:
        return self.result

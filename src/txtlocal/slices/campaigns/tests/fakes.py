import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from operator import attrgetter
from typing import TYPE_CHECKING

from txtlocal.shared.errors import BadRequest, Internal, NotFound
from txtlocal.shared.money import Micro
from txtlocal.shared.phone import E164
from txtlocal.shared.testing import RecordingBus
from txtlocal.slices.campaigns.model import (
    Campaign,
    CampaignCounter,
    CampaignCounts,
    CampaignKind,
    CampaignPage,
    CampaignQuery,
    CampaignRef,
    CampaignStatus,
    FanoutStep,
    OptOutMode,
    SchedulePlan,
)
from txtlocal.slices.campaigns.repo import PAGE_SIZE
from txtlocal.slices.campaigns.service import CampaignsService
from txtlocal.slices.identity.model import MessagingSettings, Principal, Role
from txtlocal.slices.messaging.model import BodyQuote, Product
from txtlocal.slices.messaging.policy import SendPolicy
from txtlocal.slices.messaging.segments import encoding_of, segments_of, units_of
from txtlocal.slices.senders.model import Channel, Sender, SenderKind, SenderStatus

if TYPE_CHECKING:
    from txtlocal.shared.errors import AppError

ACCOUNT_ID = "account-1"
BODY = "Hello"
FR_ONE = E164("+33612345678")
GB_ONE = E164("+447400123105")
GB_RATE = 42_700
GB_TWO = E164("+447400123100")
LEDGER_WRITE_FAILED = "the ledger write failed"
LIST_ID = "list-1"
LIST_NOT_FOUND = "List not found"
MEDIA_KEY = "media-1"
MEDIA_URL = "https://txtlocal.test/api/app/messaging/media/media-1"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
PRINCIPAL = Principal(account_id=ACCOUNT_ID, role=Role.OWNER, user_id="user-1", username="demo")
RATES = {
    ("GB", Product.SMS): GB_RATE,
    ("US", Product.SMS): 8_000,
    ("US", Product.MMS): 150_000,
}
SECRET = "unsubscribe-secret"
SHARED_POOL = "shared-pool"
SHARED_VALUE = "SHARED"
SITE = "https://txtlocal.test"
TRIAL_ENDS_AT = NOW + timedelta(days=7)
US_ONE = E164("+12025550143")


@dataclass(frozen=True, slots=True)
class FakeRecipient:
    contact_id: str
    fields: dict[str, str]
    mobile: str


def contact(mobile: str, first_name: str = "") -> FakeRecipient:
    return FakeRecipient(
        contact_id=f"contact-{mobile}",
        fields={"first_name": first_name, "mobile": mobile},
        mobile=mobile,
    )


def draft_campaign(
    recipients: Sequence[E164] = (GB_ONE, GB_TWO), created_at: datetime = NOW
) -> Campaign:
    return Campaign(
        body=BODY,
        campaign_id=str(uuid.uuid7()),
        channel=Product.SMS,
        counts=CampaignCounts(recipients=len(recipients)),
        created_at=created_at,
        kind=CampaignKind.QUICK,
        name="Quick SMS 19 Sep 2026 12:00",
        quote_micro=Micro(GB_RATE),
        recipients=list(recipients),
        reserved_micro=Micro(GB_RATE * len(recipients)),
        sender_id="smart-GB",
        shorten_urls=False,
        status=CampaignStatus.DRAFT,
        user_id=PRINCIPAL.user_id,
        username=PRINCIPAL.username,
    )


def list_campaign(
    body: str = BODY,
    footer: str = "",
    opt_out_mode: OptOutMode = OptOutMode.REPLY_STOP,
    status: CampaignStatus = CampaignStatus.DRAFT,
) -> Campaign:
    return Campaign(
        body=body,
        campaign_id=str(uuid.uuid7()),
        channel=Product.SMS,
        counts=CampaignCounts(recipients=0),
        created_at=NOW,
        footer=footer,
        kind=CampaignKind.LIST,
        list_id=LIST_ID,
        name="Helloworld",
        opt_out_mode=opt_out_mode,
        quote_micro=Micro(0),
        recipients=[],
        reserved_micro=Micro(0),
        sender_id="",
        shorten_urls=False,
        status=status,
        user_id=PRINCIPAL.user_id,
        username=PRINCIPAL.username,
    )


def policy(allowed: frozenset[str]) -> SendPolicy:
    return SendPolicy(allowed_countries=allowed, daily_cap=500, max_price_usd="0.10", sandbox=False)


@dataclass(frozen=True, slots=True)
class FakeBalance:
    balance_micro: int
    has_topped_up: bool
    trial_ends_at: datetime | None


def shared_sender(country: str, sender_id: str) -> Sender:
    return Sender(
        capabilities=(Channel.SMS,),
        country=country,
        created_at=NOW,
        kind=SenderKind.SHARED,
        provider_identity=SHARED_POOL,
        sender_id=sender_id,
        status=SenderStatus.READY,
        value=SHARED_VALUE,
    )


def alpha_sender(country: str, sender_id: str) -> Sender:
    return Sender(
        capabilities=(Channel.SMS,),
        country=country,
        created_at=NOW,
        kind=SenderKind.ALPHA,
        sender_id=sender_id,
        status=SenderStatus.READY,
        value="DemoLtd",
    )


@dataclass
class FakeBilling:
    balances: Mapping[str, FakeBalance]
    rates: Mapping[tuple[str, Product], int]
    refusal: AppError | None = None
    settle_failures: int = 0
    balance_reads: list[tuple[str, datetime]] = field(default_factory=list)
    reserved: list[tuple[str, Micro, str, datetime]] = field(default_factory=list)
    settled: list[tuple[str, str, Micro, Micro, datetime]] = field(default_factory=list)

    async def balance(self, account_id: str, now: datetime) -> FakeBalance:
        self.balance_reads.append((account_id, now))
        return self.balances[account_id]

    async def rate(self, country: str, product: Product) -> Micro:
        return Micro(self.rates[(country, product)])

    async def reserve(self, account_id: str, amount_micro: Micro, ref: str, now: datetime) -> None:
        if self.refusal is not None:
            raise self.refusal
        self.reserved.append((account_id, amount_micro, ref, now))

    async def settle(
        self, account_id: str, ref: str, reserved_micro: Micro, settled_micro: Micro, now: datetime
    ) -> None:
        if self.settle_failures:
            self.settle_failures -= 1
            raise Internal(LEDGER_WRITE_FAILED)

        self.settled.append((account_id, ref, reserved_micro, settled_micro, now))


@dataclass
class FakeContacts:
    lists: Mapping[str, Sequence[FakeRecipient]] = field(default_factory=dict)
    opted_out: frozenset[E164] = frozenset()
    opt_outs_read: list[str] = field(default_factory=list)
    reads: list[tuple[str, str]] = field(default_factory=list)
    removed: list[tuple[str, E164, datetime]] = field(default_factory=list)

    async def opt_out(self, account_id: str, mobile: E164, now: datetime) -> None:
        self.removed.append((account_id, mobile, now))

    async def opt_outs(self, account_id: str) -> frozenset[E164]:
        self.opt_outs_read.append(account_id)
        return self.opted_out

    async def recipients_of(self, account_id: str, list_id: str) -> Sequence[FakeRecipient]:
        self.reads.append((account_id, list_id))
        members = self.lists.get(list_id)
        if members is None:
            raise NotFound(LIST_NOT_FOUND)
        return members


def contacts_of(
    members: Sequence[FakeRecipient] = (), opted_out: frozenset[E164] = frozenset()
) -> FakeContacts:
    return FakeContacts(lists={LIST_ID: list(members)}, opted_out=opted_out)


MMS_MAX_CHARS = 1_500


@dataclass
class FakeQuoting:
    sent_today: int = 0
    cap_reads: list[tuple[str, datetime]] = field(default_factory=list)

    def quote(self, body: str, settings: MessagingSettings) -> BodyQuote:
        encoding = encoding_of(body)
        return BodyQuote(
            chars=units_of(body, encoding),
            encoding=encoding,
            parts=min(segments_of(body, encoding), settings.max_parts),
        )

    def quote_mms(self, body: str) -> BodyQuote:
        encoding = encoding_of(body)
        chars = units_of(body, encoding)
        if chars > MMS_MAX_CHARS:
            raise BadRequest(f"MMS content is limited to {MMS_MAX_CHARS} characters")
        return BodyQuote(chars=chars, encoding=encoding, parts=1)

    async def sends_today(self, account_id: str, now: datetime) -> int:
        self.cap_reads.append((account_id, now))
        return self.sent_today


@dataclass
class FakeMediaUrls:
    urls: Mapping[str, str] = field(default_factory=dict)

    def public_url(self, key: str) -> str:
        return self.urls.get(key, f"{SITE}/api/app/messaging/media/{key}")


@dataclass
class FakeUrlShortening:
    total_clicks: int = 0
    calls: list[tuple[str, str, str]] = field(default_factory=list)

    async def shorten_urls(
        self, body: str, account_id: str, campaign_id: str, _now: datetime
    ) -> str:
        self.calls.append((body, account_id, campaign_id))
        return body

    async def campaign_clicks_total(self, _campaign_id: str) -> int:
        return self.total_clicks


@dataclass
class FakeSenders:
    alpha: bool = False
    verified: Mapping[str, frozenset[E164]] = field(default_factory=dict)
    resolved: list[tuple[str, str | None, str]] = field(default_factory=list)

    async def resolve(self, account_id: str, sender_id: str | None, country: str) -> Sender:
        self.resolved.append((account_id, sender_id, country))
        chosen = sender_id or f"smart-{country}"
        return alpha_sender(country, chosen) if self.alpha else shared_sender(country, chosen)

    async def verified_numbers(self, account_id: str) -> frozenset[E164]:
        return self.verified.get(account_id, frozenset())


@dataclass
class FakeSettings:
    by_account: Mapping[str, MessagingSettings]

    async def messaging_settings(self, account_id: str) -> MessagingSettings:
        return self.by_account[account_id]


class InMemoryCampaignsRepo:
    def __init__(self) -> None:
        self.rows: dict[tuple[str, str], Campaign] = {}
        self.due_keys: set[tuple[str, str]] = set()
        self.sending_keys: set[tuple[str, str]] = set()

    async def add_count(
        self, account_id: str, campaign_id: str, counter: CampaignCounter, now: datetime
    ) -> Campaign:
        campaign = self.rows[(account_id, campaign_id)]
        current = campaign.counts.model_dump()[counter.value]
        counts = campaign.counts.model_copy(update={counter.value: current + 1})
        return self._store(
            account_id,
            campaign.model_copy(update={"counts": counts, "last_progress_at": now}),
        )

    async def advance_fanout(self, account_id: str, campaign_id: str, step: FanoutStep) -> Campaign:
        campaign = self.rows[(account_id, campaign_id)]
        counts = campaign.counts.model_copy(
            update={
                "queued": campaign.counts.queued + step.queued,
                "recipients": step.recipients,
                "refused": campaign.counts.refused + step.refused,
            }
        )
        if step.cursor is None:
            self.due_keys.discard((account_id, campaign_id))
            self.sending_keys.add((account_id, campaign_id))

        return self._store(
            account_id,
            campaign.model_copy(
                update={
                    "counts": counts,
                    "fanout_cursor": step.cursor,
                    "last_progress_at": step.at,
                }
            ),
        )

    async def cancel_scheduled(self, account_id: str, campaign_id: str, now: datetime) -> bool:
        campaign = self.rows[(account_id, campaign_id)]
        if campaign.status is not CampaignStatus.SCHEDULED:
            return False

        self.due_keys.discard((account_id, campaign_id))
        self._store(
            account_id,
            campaign.model_copy(
                update={
                    "completed_at": now,
                    "settled_micro": Micro(0),
                    "status": CampaignStatus.CANCELLED,
                }
            ),
        )
        return True

    async def claim_draft(self, account_id: str, campaign_id: str, now: datetime) -> bool:
        campaign = self.rows[(account_id, campaign_id)]
        if campaign.status is not CampaignStatus.DRAFT:
            return False

        self.sending_keys.add((account_id, campaign_id))
        self._store(
            account_id,
            campaign.model_copy(update={"last_progress_at": now, "status": CampaignStatus.SENDING}),
        )
        return True

    async def claim_due(
        self, account_id: str, campaign_id: str, now: datetime, stale_before: datetime
    ) -> bool:
        campaign = self.rows[(account_id, campaign_id)]
        claimed_at = campaign.claimed_at
        resumable = campaign.status is CampaignStatus.SENDING and (
            claimed_at is not None and claimed_at < stale_before
        )
        if campaign.status is not CampaignStatus.SCHEDULED and not resumable:
            return False

        self._store(
            account_id,
            campaign.model_copy(update={"claimed_at": now, "status": CampaignStatus.SENDING}),
        )
        return True

    async def clear_index(self, account_id: str, campaign_id: str) -> bool:
        if (account_id, campaign_id) not in self.rows:
            return False

        self.due_keys.discard((account_id, campaign_id))
        self.sending_keys.discard((account_id, campaign_id))
        return True

    async def complete(
        self, account_id: str, campaign_id: str, counts: CampaignCounts, now: datetime
    ) -> bool:
        campaign = self.rows[(account_id, campaign_id)]
        observed = (campaign.status, campaign.counts.sent, campaign.counts.refused)
        if observed != (CampaignStatus.SENDING, counts.sent, counts.refused):
            return False

        self.due_keys.discard((account_id, campaign_id))
        self.sending_keys.add((account_id, campaign_id))
        completed = campaign.model_copy(
            update={
                "completed_at": now,
                "last_progress_at": now,
                "status": CampaignStatus.SENT,
            }
        )
        self._store(account_id, completed)
        return True

    async def mark_settled(self, account_id: str, campaign_id: str, settled_micro: Micro) -> bool:
        campaign = self.rows[(account_id, campaign_id)]
        if campaign.status is not CampaignStatus.SENT or campaign.settled_micro is not None:
            return False

        self.due_keys.discard((account_id, campaign_id))
        self.sending_keys.discard((account_id, campaign_id))
        self._store(account_id, campaign.model_copy(update={"settled_micro": settled_micro}))
        return True

    async def delete_draft(self, account_id: str, campaign_id: str) -> bool:
        campaign = self.rows.get((account_id, campaign_id))
        if campaign is None or campaign.status is not CampaignStatus.DRAFT:
            return False
        del self.rows[(account_id, campaign_id)]
        return True

    async def due(self, now: datetime, limit: int) -> list[CampaignRef]:
        ready = [
            CampaignRef(account_id=account_id, campaign_id=campaign_id)
            for account_id, campaign_id in sorted(self.due_keys)
            if is_due(self.rows[(account_id, campaign_id)], now)
        ]
        return ready[:limit]

    async def stuck(self, before: datetime, limit: int) -> list[CampaignRef]:
        waiting = [
            CampaignRef(account_id=account_id, campaign_id=campaign_id)
            for account_id, campaign_id in sorted(self.sending_keys)
            if has_stalled(self.rows[(account_id, campaign_id)], before)
        ]
        return waiting[:limit]

    async def get(self, account_id: str, campaign_id: str) -> Campaign | None:
        return self.rows.get((account_id, campaign_id))

    async def page(self, account_id: str, query: CampaignQuery) -> CampaignPage:
        owned = [campaign for (owner, _), campaign in self.rows.items() if owner == account_id]
        matching = [campaign for campaign in owned if matches(campaign, query)]
        newest_first = sorted(matching, key=attrgetter("campaign_id"), reverse=True)
        if query.cursor is not None:
            newest_first = [c for c in newest_first if c.campaign_id < query.cursor]

        page = newest_first[:PAGE_SIZE]
        next_cursor = page[-1].campaign_id if len(newest_first) > PAGE_SIZE else None
        return CampaignPage(cursor=next_cursor, items=page)

    async def put_draft(self, account_id: str, campaign: Campaign) -> bool:
        if (account_id, campaign.campaign_id) in self.rows:
            return False
        self._store(account_id, campaign)
        return True

    async def save_draft(self, account_id: str, campaign: Campaign) -> bool:
        existing = self.rows.get((account_id, campaign.campaign_id))
        if existing is None or existing.status is not CampaignStatus.DRAFT:
            return False
        self._store(account_id, campaign)
        return True

    async def schedule(self, account_id: str, campaign_id: str, plan: SchedulePlan) -> bool:
        campaign = self.rows[(account_id, campaign_id)]
        if campaign.status is not CampaignStatus.DRAFT:
            return False

        self.due_keys.add((account_id, campaign_id))
        self._store(
            account_id,
            campaign.model_copy(
                update={
                    "counts": campaign.counts.model_copy(update={"recipients": plan.recipients}),
                    "quote_micro": plan.quote_micro,
                    "reserved_micro": plan.reserved_micro,
                    "scheduled_at": plan.scheduled_at,
                    "status": CampaignStatus.SCHEDULED,
                }
            ),
        )
        return True

    def _store(self, account_id: str, campaign: Campaign) -> Campaign:
        self.rows[(account_id, campaign.campaign_id)] = campaign
        return campaign


def is_due(campaign: Campaign, now: datetime) -> bool:
    return campaign.scheduled_at is not None and campaign.scheduled_at <= now


def has_stalled(campaign: Campaign, before: datetime) -> bool:
    return campaign.last_progress_at is not None and campaign.last_progress_at < before


def matches(campaign: Campaign, query: CampaignQuery) -> bool:
    if query.kind is not None and campaign.channel is not query.kind:
        return False
    return not query.q or query.q in campaign.name


@dataclass(frozen=True, slots=True)
class World:
    billing: FakeBilling
    bus: RecordingBus
    contacts: FakeContacts
    links: FakeUrlShortening
    repo: InMemoryCampaignsRepo
    senders: FakeSenders
    service: CampaignsService


def world(
    *,
    allowed: frozenset[str] = frozenset({"GB", "US"}),
    alpha: bool = False,
    contacts: FakeContacts | None = None,
    refusal: AppError | None = None,
    sent_today: int = 0,
    trial_ends_at: datetime | None = TRIAL_ENDS_AT,
) -> World:
    balance = FakeBalance(balance_micro=2_000_000, has_topped_up=False, trial_ends_at=trial_ends_at)
    billing = FakeBilling(balances={ACCOUNT_ID: balance}, rates=RATES, refusal=refusal)
    bus = RecordingBus()
    known = contacts if contacts is not None else FakeContacts()
    links = FakeUrlShortening()
    repo = InMemoryCampaignsRepo()
    senders = FakeSenders(alpha=alpha)
    service = CampaignsService(
        billing=billing,
        bus=bus,
        clock=lambda: NOW,
        contacts=known,
        links=links,
        media=FakeMediaUrls(),
        policy=policy(allowed),
        quoting=FakeQuoting(sent_today=sent_today),
        repo=repo,
        senders=senders,
        settings=FakeSettings({ACCOUNT_ID: MessagingSettings()}),
        site=SITE,
        unsubscribe_secret=SECRET,
    )
    return World(
        billing=billing,
        bus=bus,
        contacts=known,
        links=links,
        repo=repo,
        senders=senders,
        service=service,
    )

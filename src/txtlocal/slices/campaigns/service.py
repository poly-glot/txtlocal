import hashlib
import hmac
import itertools
import re
import uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol, assert_never

from txtlocal.shared.bus import Bus, Message, Queue
from txtlocal.shared.errors import (
    AppError,
    BadRequest,
    Conflict,
    Forbidden,
    Internal,
    NotFound,
    PaymentRequired,
    RateLimited,
)
from txtlocal.shared.money import Micro
from txtlocal.shared.phone import E164, country_of, normalise
from txtlocal.slices.analytics.model import NO_CAMPAIGN
from txtlocal.slices.campaigns.model import (
    UNPRICED,
    Campaign,
    CampaignCounter,
    CampaignCounts,
    CampaignDraft,
    CampaignKind,
    CampaignPage,
    CampaignQuery,
    CampaignQuote,
    CampaignRef,
    CampaignReport,
    CampaignStatus,
    FanOut,
    FanoutStep,
    OptOutMode,
    QuickQuote,
    QuickSendResult,
    Refusal,
    SchedulePlan,
    Settled,
)
from txtlocal.slices.messaging.gateway import DEFAULT_MEDIA_SITE, MEDIA_PATH_PREFIX, product_for
from txtlocal.slices.messaging.model import (
    CAMPAIGN_TTL_SECONDS,
    BodyQuote,
    DispatchOutcome,
    MessageType,
    Product,
    QuickSendRequest,
    RefusalReason,
    SendJob,
)
from txtlocal.slices.messaging.policy import AccountState, Allowed, Refused, SendPolicy
from txtlocal.slices.messaging.segments import Encoding, encoding_of, segments_of
from txtlocal.slices.senders.model import Sender, SenderKind, SenderView

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock
    from txtlocal.slices.campaigns.repo import CampaignsRepo
    from txtlocal.slices.identity.model import MessagingSettings, Principal
ALPHA_NEEDS_LINK = "Replies are not possible from an alpha tag; choose Unsubscribe Link"
CAMPAIGN_NOT_FOUND = "Campaign not found"
CAMPAIGN_SENDING = "This campaign is already sending"
CLAIMABLE = frozenset({CampaignStatus.SCHEDULED, CampaignStatus.SENDING})
COPY_SUFFIX = " (copy)"
DIGEST_CHARS = 32
DRAFT_ONLY = "Only a draft campaign can be changed"
DUE_LIMIT = 25
FANOUT_UNBOUNDED = "the fan-out read more batches than its cap"
LINK_FIELD = "unsubscribe_link"
MAX_FANOUT_BATCHES = 1_000
MAX_RECIPIENTS = 1_000
NEEDS_BODY = "Write the message your contacts will receive"
NEEDS_LIST = "Select the list this campaign sends to"
NEEDS_MEDIA = "Attach an image to send an MMS"
NOT_SCHEDULED = "Only a scheduled campaign can be cancelled"
NO_RECIPIENTS = "Add at least one recipient"
NO_TRIAL = datetime.min.replace(tzinfo=UTC)
QUOTE_SAMPLE = 100
REPLY_STOP_FOOTER = "Reply STOP to opt-out"
SCHEDULE_EARLIEST = timedelta(minutes=5)
SCHEDULE_LATEST = timedelta(days=365)
SCHEDULE_TOO_LATE = "Schedule a campaign at most twelve months ahead"
SCHEDULE_TOO_SOON = "Schedule a campaign at least five minutes ahead"
SEND_JOB_BATCH = 10
SETTLING_COUNTERS = frozenset({CampaignCounter.REFUSED, CampaignCounter.SENT})
STALE_CLAIM = timedelta(seconds=60)
STUCK_AFTER = timedelta(hours=1)
LINK_SEPARATOR = "."
TOO_MANY_RECIPIENTS = "Send to at most 1,000 recipients at a time"
UNKNOWN_LINK = "That link is no longer valid"
UNSUBSCRIBED_PAGE = "You have been unsubscribed."
UNSUBSCRIBE_FOOTER = f"Unsubscribe: {{{LINK_FIELD}}}"
UNSUBSCRIBE_PATH = "/api/u/"

PLACEHOLDER_FIELDS = (
    "cf1",
    "cf2",
    "cf3",
    "cf4",
    "email",
    "first_name",
    "last_name",
    "mobile",
    LINK_FIELD,
)
PLACEHOLDER = re.compile(r"\{(" + "|".join(PLACEHOLDER_FIELDS) + r")\}")


class Balance(Protocol):
    @property
    def balance_micro(self) -> int: ...

    @property
    def has_topped_up(self) -> bool: ...

    @property
    def trial_ends_at(self) -> datetime | None: ...


class Billing(Protocol):
    async def balance(self, account_id: str, now: datetime) -> Balance: ...

    async def rate(self, country: str, product: Product) -> Micro: ...

    async def reserve(
        self, account_id: str, amount_micro: Micro, ref: str, now: datetime
    ) -> None: ...

    async def settle(
        self, account_id: str, ref: str, reserved_micro: Micro, settled_micro: Micro, now: datetime
    ) -> None: ...


class Recipient(Protocol):
    @property
    def contact_id(self) -> str: ...

    @property
    def fields(self) -> dict[str, str]: ...

    @property
    def mobile(self) -> str: ...


class Contacts(Protocol):
    async def opt_out(self, account_id: str, mobile: E164, now: datetime) -> None: ...

    async def opt_outs(self, account_id: str) -> frozenset[E164]: ...

    async def recipients_of(self, account_id: str, list_id: str) -> Sequence[Recipient]: ...


class Quoting(Protocol):
    def quote(self, body: str, settings: MessagingSettings) -> BodyQuote: ...

    def quote_mms(self, body: str) -> BodyQuote: ...

    async def sends_today(self, account_id: str, now: datetime) -> int: ...


class SenderResolution(Protocol):
    async def resolve(self, account_id: str, sender_id: str | None, country: str) -> Sender: ...

    async def verified_numbers(self, account_id: str) -> frozenset[E164]: ...


class Settings(Protocol):
    async def messaging_settings(self, account_id: str) -> MessagingSettings: ...


class TrackedLinks(Protocol):
    async def campaign_clicks_total(self, campaign_id: str) -> int: ...

    async def shorten_urls(
        self, body: str, account_id: str, campaign_id: str, now: datetime
    ) -> str: ...


class MediaUrls(Protocol):
    def public_url(self, key: str) -> str: ...


@dataclass(frozen=True, slots=True)
class DefaultMediaUrls:
    def public_url(self, key: str) -> str:
        return f"{DEFAULT_MEDIA_SITE}{MEDIA_PATH_PREFIX}{key}"


@dataclass(frozen=True, slots=True)
class Accepted:
    body: str
    country: str
    price_micro: Micro
    product: Product
    sender: SenderView
    to: E164


@dataclass(frozen=True, slots=True)
class Assessment:
    accepted: list[Accepted]
    cost_micro: Micro
    quote: BodyQuote
    refused: list[Refusal]


@dataclass(frozen=True, slots=True)
class Addressed:
    country: str
    mobile: E164
    recipient: Recipient


@dataclass(frozen=True, slots=True)
class ListQuote:
    cost_micro: Micro
    parts: int
    quote_micro: Micro
    recipients: int
    sender: SenderView


@dataclass(frozen=True, slots=True)
class FanoutPlan:
    account_id: str
    campaign: Campaign
    media_url: str
    opted_out: frozenset[E164]
    secret: str
    senders: Mapping[str, SenderView]
    site: str
    template: str


@dataclass(frozen=True, slots=True)
class RawRecipient:
    mobile: str

    @property
    def contact_id(self) -> str:
        return ""

    @property
    def fields(self) -> dict[str, str]:
        return {}


def unique_recipients(
    listed: Sequence[Recipient], typed: Iterable[str], default_country: str
) -> list[Addressed]:
    merged: dict[E164, Recipient] = {}
    for recipient in [*listed, *(RawRecipient(mobile=number) for number in typed)]:
        mobile = normalise(recipient.mobile, default_country)
        if is_richer(recipient, merged.get(mobile)):
            merged[mobile] = recipient

    return [addressed_of(recipient, mobile) for mobile, recipient in merged.items()]


def per_message_quote(cost_micro: Micro, recipients: int) -> Micro:
    return Micro((cost_micro + recipients - 1) // recipients)


def quick_name(channel: Product, now: datetime) -> str:
    return f"Quick {channel} {now:%d %b %Y %H:%M}"


def origination_of(sender: SenderView) -> str:
    return sender.provider_identity or sender.value


def render(template: str, fields: Mapping[str, str]) -> str:
    return PLACEHOLDER.sub(lambda found: fields.get(found[1], ""), template)


def with_footer(body: str, footer: str) -> str:
    return f"{body}\n{footer}" if footer else body


def default_footer(mode: OptOutMode) -> str:
    match mode:
        case OptOutMode.REPLY_STOP:
            return REPLY_STOP_FOOTER
        case OptOutMode.UNSUBSCRIBE_LINK:
            return UNSUBSCRIBE_FOOTER
        case _ as unreachable:
            assert_never(unreachable)


def digest_of(secret: str, payload: str) -> str:
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return urlsafe_b64encode(signature).decode()[:DIGEST_CHARS]


def encoded(payload: str) -> str:
    return urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decoded(text: str) -> str | None:
    try:
        return urlsafe_b64decode(text + "=" * (-len(text) % 4)).decode()
    except UnicodeDecodeError, ValueError:
        return None


def unsubscribe_token(secret: str, account_id: str, mobile: str) -> str:
    payload = f"{account_id}:{mobile}"
    return f"{digest_of(secret, payload)}{LINK_SEPARATOR}{encoded(payload)}"


def unsubscribed_of(secret: str, token: str) -> tuple[str, E164] | None:
    digest, separator, body = token.partition(LINK_SEPARATOR)
    payload = decoded(body) if separator else None
    if payload is None:
        return None

    account_id, colon, mobile = payload.partition(":")
    if not (colon and account_id and mobile):
        return None
    if not hmac.compare_digest(digest, digest_of(secret, payload)):
        return None

    return account_id, E164(mobile)


def unsubscribe_link(plan: FanoutPlan, mobile: E164) -> str:
    if plan.campaign.opt_out_mode is OptOutMode.REPLY_STOP:
        return ""
    token = unsubscribe_token(plan.secret, plan.account_id, mobile)
    return f"{plan.site}{UNSUBSCRIBE_PATH}{token}"


def resolved_body(template: str, recipient: Recipient, link: str) -> str:
    return render(template, {**recipient.fields, LINK_FIELD: link})


def with_media_link(body: str, product: Product, media_url: str) -> str:
    return f"{body}\n\n{media_url}" if product is Product.MMS_AS_LINK else body


def link_parts_of(body: str, media_url: str) -> int:
    if not media_url:
        return segments_of(body, encoding_of(body))
    linked = with_media_link(body, Product.MMS_AS_LINK, media_url)
    return segments_of(linked, encoding_of(linked))


def billed_parts(product: Product, quote: BodyQuote, link_parts: int) -> int:
    match product:
        case Product.SMS:
            return quote.parts
        case Product.MMS:
            return 1
        case Product.MMS_AS_LINK:
            return link_parts
        case _ as unreachable:
            assert_never(unreachable)


def parts_of(product: Product, body: str, encoding: Encoding) -> int:
    return 1 if product is Product.MMS else segments_of(body, encoding)


def rate_product_of(product: Product) -> Product:
    return Product.SMS if product is Product.MMS_AS_LINK else product


def campaign_body(plan: FanoutPlan, one: Addressed, product: Product) -> str:
    resolved = resolved_body(plan.template, one.recipient, unsubscribe_link(plan, one.mobile))
    return with_media_link(resolved, product, plan.media_url)


def longest_body(plan: FanoutPlan, sample: Sequence[Addressed]) -> str:
    return max(
        (
            resolved_body(plan.template, one.recipient, unsubscribe_link(plan, one.mobile))
            for one in sample
        ),
        key=len,
        default=plan.template,
    )


def addressed_of(recipient: Recipient, mobile: E164) -> Addressed:
    return Addressed(country=country_of(mobile), mobile=mobile, recipient=recipient)


def is_richer(candidate: Recipient, current: Recipient | None) -> bool:
    return current is None or (bool(candidate.fields) and not current.fields)


def plan_of(campaign: Campaign, scheduled_at: datetime) -> SchedulePlan:
    return SchedulePlan(
        quote_micro=campaign.quote_micro,
        recipients=campaign.counts.recipients,
        reserved_micro=campaign.reserved_micro,
        scheduled_at=scheduled_at,
    )


def missing_of(counts: CampaignCounts) -> int:
    return counts.recipients - counts.sent - counts.refused


def settled_of(campaign: Campaign) -> Micro:
    return Micro(campaign.quote_micro * campaign.counts.sent)


def settled_report(campaign: Campaign) -> Settled:
    return Settled(
        campaign_id=campaign.campaign_id,
        missing=missing_of(campaign.counts),
        settled_micro=settled_of(campaign),
    )


def is_unsettled(campaign: Campaign) -> bool:
    return campaign.status is CampaignStatus.SENT and campaign.settled_micro is None


def is_abandoned_fanout(campaign: Campaign, now: datetime) -> bool:
    progressed_at = campaign.last_progress_at or campaign.claimed_at
    if campaign.status is not CampaignStatus.SENDING or progressed_at is None:
        return False
    return progressed_at <= now - STUCK_AFTER


def scheduled_time(send_at: datetime | None, now: datetime) -> datetime:
    if send_at is None:
        return now
    if send_at < now + SCHEDULE_EARLIEST:
        raise BadRequest(SCHEDULE_TOO_SOON)
    if send_at > now + SCHEDULE_LATEST:
        raise BadRequest(SCHEDULE_TOO_LATE)
    return send_at


def replies_are_possible(mode: OptOutMode, sender: SenderView) -> None:
    if mode is OptOutMode.REPLY_STOP and sender.kind is SenderKind.ALPHA:
        raise BadRequest(ALPHA_NEEDS_LINK)


def quote_time_state(
    balance: Balance,
    opted_out: frozenset[E164],
    sends_today: int,
    verified_numbers: frozenset[E164],
) -> AccountState:
    return AccountState(
        balance_micro=Micro(balance.balance_micro),
        has_topped_up=balance.has_topped_up,
        opted_out=opted_out,
        sends_today=sends_today,
        trial_ends_at=balance.trial_ends_at or NO_TRIAL,
        verified_numbers=verified_numbers,
    )


def counter_of(outcome: DispatchOutcome) -> CampaignCounter | None:
    match outcome:
        case DispatchOutcome.ACCEPTED:
            return CampaignCounter.SENT
        case DispatchOutcome.REFUSED:
            return CampaignCounter.REFUSED
        case DispatchOutcome.DUPLICATE:
            return None
        case _:
            assert_never(outcome)


def drafted(
    principal: Principal, draft: CampaignDraft, campaign_id: str, created_at: datetime
) -> Campaign:
    return Campaign(
        body=draft.body,
        campaign_id=campaign_id,
        channel=draft.product,
        counts=CampaignCounts(recipients=0),
        created_at=created_at,
        footer=draft.footer or default_footer(draft.opt_out_mode),
        kind=CampaignKind.LIST,
        list_id=draft.list_id,
        media_key=draft.media_key,
        name=draft.name,
        opt_out_mode=draft.opt_out_mode,
        quote_micro=UNPRICED,
        recipients=[],
        reserved_micro=UNPRICED,
        sender_id=draft.sender_id,
        shorten_urls=draft.shorten_urls,
        status=CampaignStatus.DRAFT,
        subject=draft.subject,
        user_id=principal.user_id,
        username=principal.username,
    )


def draft_of(campaign: Campaign) -> CampaignDraft:
    return CampaignDraft(
        body=campaign.body,
        footer=campaign.footer,
        list_id=campaign.list_id,
        media_key=campaign.media_key,
        name=f"{campaign.name}{COPY_SUFFIX}",
        opt_out_mode=campaign.opt_out_mode,
        product=campaign.channel,
        sender_id=campaign.sender_id,
        shorten_urls=campaign.shorten_urls,
        subject=campaign.subject,
    )


def quick_campaign(
    principal: Principal, request: QuickSendRequest, assessed: Assessment, now: datetime
) -> Campaign:
    accepted = assessed.accepted
    return Campaign(
        body=request.body,
        campaign_id=str(uuid.uuid7()),
        channel=request.kind,
        counts=CampaignCounts(recipients=len(accepted)),
        created_at=now,
        kind=CampaignKind.QUICK,
        list_ids=list(request.list_ids),
        media_key=request.media_key,
        name=quick_name(request.kind, now),
        quote_micro=per_message_quote(assessed.cost_micro, len(accepted)),
        recipients=[recipient.to for recipient in accepted],
        reserved_micro=assessed.cost_micro,
        sender_id=request.sender_id or accepted[0].sender.sender_id,
        shorten_urls=request.shorten_urls,
        status=CampaignStatus.DRAFT,
        subject=request.subject or None,
        user_id=principal.user_id,
        username=principal.username,
    )


def send_job(
    principal: Principal, campaign: Campaign, recipient: Accepted, message_type: MessageType
) -> Message:
    encoding = encoding_of(recipient.body)
    is_mms = recipient.product is Product.MMS
    job = SendJob(
        account_id=principal.account_id,
        body=recipient.body,
        campaign_id=campaign.campaign_id,
        country=recipient.country,
        encoding=encoding,
        media_key=campaign.media_key if is_mms else None,
        message_type=message_type,
        origination=origination_of(recipient.sender),
        parts=parts_of(recipient.product, recipient.body, encoding),
        price_micro=recipient.price_micro,
        product=recipient.product,
        sender_id=recipient.sender.sender_id,
        sender_kind=recipient.sender.kind,
        sender_value=recipient.sender.value,
        subject=(campaign.subject or "") if is_mms else "",
        to=recipient.to,
        user_id=principal.user_id,
        username=principal.username,
    )
    return Message(body=job.model_dump_json())


def campaign_job(plan: FanoutPlan, one: Addressed) -> Message:
    campaign = plan.campaign
    product = product_for(campaign.channel, one.country)
    is_mms = product is Product.MMS
    body = campaign_body(plan, one, product)
    encoding = encoding_of(body)
    sender = plan.senders[one.country]
    job = SendJob(
        account_id=plan.account_id,
        body=body,
        campaign_id=campaign.campaign_id,
        country=one.country,
        encoding=encoding,
        media_key=campaign.media_key if is_mms else None,
        message_type=MessageType.PROMOTIONAL,
        origination=origination_of(sender),
        parts=parts_of(product, body, encoding),
        price_micro=campaign.quote_micro,
        product=product,
        sender_id=sender.sender_id,
        sender_kind=sender.kind,
        sender_value=sender.value,
        subject=(campaign.subject or "") if is_mms else "",
        to=one.mobile,
        ttl_seconds=CAMPAIGN_TTL_SECONDS,
        user_id=campaign.user_id,
        username=campaign.username,
    )
    return Message(body=job.model_dump_json())


def is_sendable(plan: FanoutPlan, one: Addressed, allowed_countries: frozenset[str]) -> bool:
    if one.mobile in plan.opted_out:
        return False
    return one.country in allowed_countries


def refusal_error(refusal: Refusal) -> AppError:
    match refusal.reason:
        case RefusalReason.INSUFFICIENT_BALANCE:
            return PaymentRequired(refusal.message)
        case RefusalReason.TRIAL_ENDED:
            return Forbidden(refusal.message)
        case RefusalReason.DAILY_CAP:
            return RateLimited(refusal.message)
        case _:
            return BadRequest(refusal.message)


@dataclass(frozen=True, slots=True)
class CampaignsService:
    billing: Billing
    bus: Bus
    clock: Clock
    contacts: Contacts
    links: TrackedLinks
    policy: SendPolicy
    quoting: Quoting
    repo: CampaignsRepo
    senders: SenderResolution
    settings: Settings
    site: str
    unsubscribe_secret: str
    media: MediaUrls = field(default_factory=DefaultMediaUrls)

    async def quote_quick(
        self, principal: Principal, request: QuickSendRequest, now: datetime
    ) -> QuickQuote:
        assessed = await self._assess(principal.account_id, request, now)
        return QuickQuote(
            cost_micro=assessed.cost_micro,
            parts=assessed.quote.parts,
            recipients=len(assessed.accepted),
            refused=assessed.refused,
        )

    async def send_quick(
        self, principal: Principal, request: QuickSendRequest, now: datetime
    ) -> QuickSendResult:
        scheduled_at = None if request.send_at is None else scheduled_time(request.send_at, now)

        assessed = await self._assess(principal.account_id, request, now)
        if not assessed.accepted:
            raise refusal_error(assessed.refused[0])

        campaign = quick_campaign(principal, request, assessed, now)
        if not await self.repo.put_draft(principal.account_id, campaign):
            raise Internal(f"campaign {campaign.campaign_id} already exists")

        await self.billing.reserve(
            principal.account_id, campaign.reserved_micro, campaign.campaign_id, now
        )
        if scheduled_at is None:
            await self._fan_out_now(principal, campaign, assessed, request.message_type, now)
        else:
            await self._schedule(principal.account_id, campaign, plan_of(campaign, scheduled_at))

        return QuickSendResult(
            campaign_id=campaign.campaign_id,
            cost_micro=campaign.reserved_micro,
            recipients=len(assessed.accepted),
            refused=assessed.refused,
        )

    async def create_draft(
        self, principal: Principal, draft: CampaignDraft, now: datetime
    ) -> Campaign:
        campaign_id = str(uuid.uuid7())
        draft = await self._shortened_draft(principal.account_id, draft, campaign_id, now)
        campaign = drafted(principal, draft, campaign_id, now)
        if not await self.repo.put_draft(principal.account_id, campaign):
            raise Internal(f"campaign {campaign.campaign_id} already exists")
        return campaign

    async def save_draft(
        self, principal: Principal, campaign_id: str, draft: CampaignDraft, now: datetime
    ) -> Campaign:
        draft = await self._shortened_draft(principal.account_id, draft, campaign_id, now)
        campaign = drafted(principal, draft, campaign_id, now)
        if not await self.repo.save_draft(principal.account_id, campaign):
            raise await self._draft_refusal(principal.account_id, campaign_id)
        return campaign

    async def _shortened_draft(
        self, account_id: str, draft: CampaignDraft, campaign_id: str, now: datetime
    ) -> CampaignDraft:
        if not draft.shorten_urls:
            return draft
        body = await self.links.shorten_urls(draft.body, account_id, campaign_id, now)
        return draft.model_copy(update={"body": body})

    async def delete_draft(self, principal: Principal, campaign_id: str) -> None:
        if not await self.repo.delete_draft(principal.account_id, campaign_id):
            raise await self._draft_refusal(principal.account_id, campaign_id)

    async def quote(self, principal: Principal, campaign_id: str, now: datetime) -> CampaignQuote:
        campaign = await self.get(principal.account_id, campaign_id)
        quoted = await self._quote_list(principal.account_id, campaign, now)
        return CampaignQuote(
            cost_micro=quoted.cost_micro,
            parts=quoted.parts,
            recipients=quoted.recipients,
            sender_display=quoted.sender.display,
        )

    async def schedule(
        self, principal: Principal, campaign_id: str, send_at: datetime | None, now: datetime
    ) -> Campaign:
        campaign = await self.get(principal.account_id, campaign_id)
        if campaign.status is not CampaignStatus.DRAFT:
            raise Conflict(DRAFT_ONLY)

        scheduled_at = scheduled_time(send_at, now)
        quoted = await self._quote_list(principal.account_id, campaign, now)
        await self.billing.reserve(principal.account_id, quoted.cost_micro, campaign_id, now)

        plan = SchedulePlan(
            quote_micro=quoted.quote_micro,
            recipients=quoted.recipients,
            reserved_micro=quoted.cost_micro,
            scheduled_at=scheduled_at,
        )
        return await self._schedule(principal.account_id, campaign, plan)

    async def cancel(self, principal: Principal, campaign_id: str, now: datetime) -> Campaign:
        campaign = await self.get(principal.account_id, campaign_id)
        if campaign.status is CampaignStatus.SENDING:
            raise Conflict(CAMPAIGN_SENDING)
        if campaign.status is not CampaignStatus.SCHEDULED:
            raise Conflict(NOT_SCHEDULED)

        if not await self.repo.cancel_scheduled(principal.account_id, campaign_id, now):
            raise Conflict(CAMPAIGN_SENDING)

        await self.billing.settle(
            principal.account_id, campaign_id, campaign.reserved_micro, UNPRICED, now
        )
        return campaign.model_copy(
            update={
                "completed_at": now,
                "settled_micro": UNPRICED,
                "status": CampaignStatus.CANCELLED,
            }
        )

    async def duplicate(self, principal: Principal, campaign_id: str, now: datetime) -> Campaign:
        source = await self.get(principal.account_id, campaign_id)
        return await self.create_draft(principal, draft_of(source), now)

    async def report(self, principal: Principal, campaign_id: str) -> CampaignReport:
        campaign = await self.get(principal.account_id, campaign_id)
        clicks = await self.links.campaign_clicks_total(campaign_id)
        return CampaignReport(campaign=campaign, clicks=clicks)

    async def due(self, now: datetime, limit: int) -> list[CampaignRef]:
        return await self.repo.due(now, limit)

    async def claim_and_fan_out(self, ref: CampaignRef, now: datetime) -> FanOut:
        campaign = await self.repo.get(ref.account_id, ref.campaign_id)
        if campaign is None or campaign.status not in CLAIMABLE:
            return FanOut(campaign_id=ref.campaign_id, skipped=True)

        if not await self.repo.claim_due(ref.account_id, ref.campaign_id, now, now - STALE_CLAIM):
            return FanOut(campaign_id=ref.campaign_id, skipped=True)

        if is_abandoned_fanout(campaign, now):
            await self._complete(ref.account_id, campaign, now)
            return FanOut(campaign_id=ref.campaign_id, skipped=True)

        return await self._fan_out(ref.account_id, campaign, now)

    async def stuck(self, now: datetime, limit: int) -> list[CampaignRef]:
        return await self.repo.stuck(now - STUCK_AFTER, limit)

    async def settle_stuck(self, ref: CampaignRef, now: datetime) -> Settled:
        campaign = await self.repo.get(ref.account_id, ref.campaign_id)
        if campaign is None:
            return Settled(campaign_id=ref.campaign_id, skipped=True)

        if is_unsettled(campaign):
            await self._settle_reservation(ref.account_id, campaign, now)
            return settled_report(campaign)

        if campaign.status is not CampaignStatus.SENDING:
            await self.repo.clear_index(ref.account_id, ref.campaign_id)
            return Settled(campaign_id=ref.campaign_id, skipped=True)

        if not await self._complete(ref.account_id, campaign, now):
            return Settled(campaign_id=ref.campaign_id, skipped=True)

        return settled_report(campaign)

    async def unsubscribe(self, token: str, now: datetime) -> None:
        unsubscribed = unsubscribed_of(self.unsubscribe_secret, token)
        if unsubscribed is None:
            raise NotFound(UNKNOWN_LINK)

        account_id, mobile = unsubscribed
        await self.contacts.opt_out(account_id, mobile, now)

    async def record_outcome(
        self, account_id: str, campaign_id: str, outcome: DispatchOutcome, now: datetime
    ) -> None:
        counter = counter_of(outcome)
        if counter is not None:
            await self._count(account_id, campaign_id, counter, now)

    async def record_delivery(
        self, account_id: str, campaign_id: str, *, delivered: bool, now: datetime
    ) -> None:
        counter = CampaignCounter.DELIVERED if delivered else CampaignCounter.UNDELIVERED
        await self._count(account_id, campaign_id, counter, now)

    async def list(self, account_id: str, query: CampaignQuery) -> CampaignPage:
        return await self.repo.page(account_id, query)

    async def get(self, account_id: str, campaign_id: str) -> Campaign:
        campaign = await self.repo.get(account_id, campaign_id)
        if campaign is None:
            raise NotFound(CAMPAIGN_NOT_FOUND)
        return campaign

    async def _draft_refusal(self, account_id: str, campaign_id: str) -> AppError:
        if await self.repo.get(account_id, campaign_id) is None:
            return NotFound(CAMPAIGN_NOT_FOUND)
        return Conflict(DRAFT_ONLY)

    async def _schedule(self, account_id: str, campaign: Campaign, plan: SchedulePlan) -> Campaign:
        if not await self.repo.schedule(account_id, campaign.campaign_id, plan):
            raise Conflict(DRAFT_ONLY)

        return campaign.model_copy(
            update={
                "counts": campaign.counts.model_copy(update={"recipients": plan.recipients}),
                "quote_micro": plan.quote_micro,
                "reserved_micro": plan.reserved_micro,
                "scheduled_at": plan.scheduled_at,
                "status": CampaignStatus.SCHEDULED,
            }
        )

    async def _fan_out_now(
        self,
        principal: Principal,
        campaign: Campaign,
        assessed: Assessment,
        message_type: MessageType,
        now: datetime,
    ) -> None:
        if not await self.repo.claim_draft(principal.account_id, campaign.campaign_id, now):
            raise Internal(f"campaign {campaign.campaign_id} is not a draft")

        jobs = [send_job(principal, campaign, r, message_type) for r in assessed.accepted]
        for batch in itertools.batched(jobs, SEND_JOB_BATCH, strict=False):
            await self.bus.send(Queue.SEND_JOBS, batch)

    async def _fan_out(self, account_id: str, campaign: Campaign, now: datetime) -> FanOut:
        addressed = await self._addressed(account_id, campaign)
        opted_out = await self.contacts.opt_outs(account_id)
        plan = await self._plan(account_id, campaign, addressed, opted_out)

        cursor = int(campaign.fanout_cursor or 0)
        queued = 0
        for _ in range(MAX_FANOUT_BATCHES):
            batch = addressed[cursor : cursor + SEND_JOB_BATCH]
            jobs = [
                campaign_job(plan, one)
                for one in batch
                if is_sendable(plan, one, self.policy.allowed_countries)
            ]
            if jobs:
                await self.bus.send(Queue.SEND_JOBS, jobs)

            cursor += len(batch)
            queued += len(jobs)
            done = cursor >= len(addressed)
            row = await self.repo.advance_fanout(
                account_id,
                campaign.campaign_id,
                FanoutStep(
                    at=now,
                    cursor=None if done else str(cursor),
                    queued=len(jobs),
                    recipients=len(addressed),
                    refused=len(batch) - len(jobs),
                ),
            )
            if done:
                await self._settle(account_id, row, now)
                return FanOut(
                    campaign_id=campaign.campaign_id, queued=queued, recipients=len(addressed)
                )

        raise Internal(FANOUT_UNBOUNDED)

    async def _plan(
        self,
        account_id: str,
        campaign: Campaign,
        addressed: Sequence[Addressed],
        opted_out: frozenset[E164],
    ) -> FanoutPlan:
        countries = {
            one.country for one in addressed if one.country in self.policy.allowed_countries
        }
        return FanoutPlan(
            account_id=account_id,
            campaign=campaign,
            media_url=self._media_url(campaign.channel, campaign.media_key),
            opted_out=opted_out,
            secret=self.unsubscribe_secret,
            senders=await self._senders_for(account_id, campaign.sender_id, countries),
            site=self.site,
            template=with_footer(campaign.body, campaign.footer),
        )

    async def _senders_for(
        self, account_id: str, sender_id: str, countries: Iterable[str]
    ) -> dict[str, SenderView]:
        return {
            country: SenderView.of(
                await self.senders.resolve(account_id, sender_id or None, country)
            )
            for country in sorted(countries)
        }

    async def _addressed(self, account_id: str, campaign: Campaign) -> Sequence[Addressed]:
        recipients = await self._recipients_of(account_id, campaign)
        return [addressed_of(recipient, E164(recipient.mobile)) for recipient in recipients]

    async def _recipients_of(self, account_id: str, campaign: Campaign) -> Sequence[Recipient]:
        if campaign.kind is CampaignKind.QUICK:
            listed = {
                one.mobile: one
                for one in await self._listed_recipients(account_id, campaign.list_ids)
            }
            return [
                listed.get(mobile, RawRecipient(mobile=mobile)) for mobile in campaign.recipients
            ]
        if campaign.list_id is None:
            raise BadRequest(NEEDS_LIST)
        return await self.contacts.recipients_of(account_id, campaign.list_id)

    async def _quote_list(self, account_id: str, campaign: Campaign, now: datetime) -> ListQuote:
        if campaign.channel is Product.MMS:
            if campaign.media_key is None:
                raise BadRequest(NEEDS_MEDIA)
        elif not campaign.body:
            raise BadRequest(NEEDS_BODY)

        addressed = await self._addressed(account_id, campaign)
        chargeable = Counter(
            one.country for one in addressed if one.country in self.policy.allowed_countries
        )
        if not chargeable:
            raise BadRequest(NO_RECIPIENTS)

        plan = await self._plan(account_id, campaign, addressed, frozenset())
        sender = plan.senders[next(iter(chargeable))]
        replies_are_possible(campaign.opt_out_mode, sender)

        settings = await self.settings.messaging_settings(account_id)
        representative = longest_body(plan, addressed[:QUOTE_SAMPLE])
        quote = self._quote_of(campaign.channel, representative, settings)
        link_parts = link_parts_of(representative, plan.media_url)
        products = {country: product_for(campaign.channel, country) for country in chargeable}
        rates = {
            country: Micro(
                await self.billing.rate(country, rate_product_of(products[country]))
                * billed_parts(products[country], quote, link_parts)
            )
            for country in chargeable
        }
        cost = Micro(sum(rates[country] * count for country, count in chargeable.items()))

        recipients = sum(chargeable.values())
        await self._check_policy(account_id, addressed, sender, cost, now)
        return ListQuote(
            cost_micro=cost,
            parts=quote.parts,
            quote_micro=per_message_quote(cost, recipients),
            recipients=recipients,
            sender=sender,
        )

    async def _check_policy(
        self,
        account_id: str,
        addressed: Sequence[Addressed],
        sender: SenderView,
        cost: Micro,
        now: datetime,
    ) -> None:
        account = await self._quote_time_state(account_id, frozenset(), now)
        destination = next(
            one.mobile for one in addressed if one.country in self.policy.allowed_countries
        )
        match self.policy.allow(account, sender, destination, cost, now):
            case Refused(message=message):
                raise BadRequest(message)
            case Allowed():
                return
            case _ as unreachable:
                assert_never(unreachable)

    async def _count(
        self, account_id: str, campaign_id: str, counter: CampaignCounter, now: datetime
    ) -> None:
        campaign = await self.repo.add_count(account_id, campaign_id, counter, now)
        if counter in SETTLING_COUNTERS:
            await self._settle(account_id, campaign, now)

    async def _settle(self, account_id: str, campaign: Campaign, now: datetime) -> None:
        if missing_of(campaign.counts) == 0:
            await self._complete(account_id, campaign, now)

    async def _complete(self, account_id: str, campaign: Campaign, now: datetime) -> bool:
        if not await self.repo.complete(account_id, campaign.campaign_id, campaign.counts, now):
            return False

        await self._settle_reservation(account_id, campaign, now)
        return True

    async def _settle_reservation(self, account_id: str, campaign: Campaign, now: datetime) -> None:
        settled = settled_of(campaign)
        await self.billing.settle(
            account_id, campaign.campaign_id, campaign.reserved_micro, settled, now
        )
        await self.repo.mark_settled(account_id, campaign.campaign_id, settled)

    async def _assess(
        self, account_id: str, request: QuickSendRequest, now: datetime
    ) -> Assessment:
        if request.kind is Product.MMS and request.media_key is None:
            raise BadRequest(NEEDS_MEDIA)

        settings = await self.settings.messaging_settings(account_id)
        listed = await self._listed_recipients(account_id, request.list_ids)
        addressed = unique_recipients(listed, request.to, settings.default_country)
        if not addressed:
            raise BadRequest(NO_RECIPIENTS)
        if len(addressed) > MAX_RECIPIENTS:
            raise BadRequest(TOO_MANY_RECIPIENTS)

        body = await self._shortened_body(account_id, request, now)
        bodies = {one.mobile: resolved_body(body, one.recipient, "") for one in addressed}
        representative = max(bodies.values(), key=len)
        quote = self._quote_of(request.kind, representative, settings)
        media_url = self._media_url(request.kind, request.media_key)
        link_parts = link_parts_of(representative, media_url)

        countries = {one.country for one in addressed}
        products = {country: product_for(request.kind, country) for country in countries}
        senders = await self._senders_for(account_id, request.sender_id or "", countries)
        prices = {
            country: Micro(
                await self.billing.rate(country, rate_product_of(products[country]))
                * billed_parts(products[country], quote, link_parts)
            )
            for country in countries & self.policy.allowed_countries
        }
        opted_out = await self.contacts.opt_outs(account_id)
        account = await self._quote_time_state(account_id, opted_out, now)

        accepted: list[Accepted] = []
        refused: list[Refusal] = []
        for one in addressed:
            product = products[one.country]
            price = prices.get(one.country, UNPRICED)
            sender = senders[one.country]
            match self.policy.allow(account, sender, one.mobile, price, now):
                case Refused(message=message, reason=reason):
                    refused.append(Refusal(message=message, reason=reason, to=one.mobile))
                case Allowed():
                    accepted.append(
                        Accepted(
                            body=with_media_link(bodies[one.mobile], product, media_url),
                            country=one.country,
                            price_micro=price,
                            product=product,
                            sender=sender,
                            to=one.mobile,
                        )
                    )
                case _ as unreachable:
                    assert_never(unreachable)

        return Assessment(
            accepted=accepted,
            cost_micro=Micro(sum(recipient.price_micro for recipient in accepted)),
            quote=quote,
            refused=refused,
        )

    def _media_url(self, kind: Product, media_key: str | None) -> str:
        if kind is not Product.MMS or media_key is None:
            return ""
        return self.media.public_url(media_key)

    def _quote_of(self, kind: Product, body: str, settings: MessagingSettings) -> BodyQuote:
        if kind is Product.MMS:
            return self.quoting.quote_mms(body)
        return self.quoting.quote(body, settings)

    async def _shortened_body(
        self, account_id: str, request: QuickSendRequest, now: datetime
    ) -> str:
        if not request.shorten_urls:
            return request.body
        return await self.links.shorten_urls(request.body, account_id, NO_CAMPAIGN, now)

    async def _listed_recipients(
        self, account_id: str, list_ids: Sequence[str]
    ) -> Sequence[Recipient]:
        lists = [await self.contacts.recipients_of(account_id, list_id) for list_id in list_ids]
        return [recipient for members in lists for recipient in members]

    async def _quote_time_state(
        self, account_id: str, opted_out: frozenset[E164], now: datetime
    ) -> AccountState:
        balance = await self.billing.balance(account_id, now)
        sends_today = await self.quoting.sends_today(account_id, now)
        verified = await self.senders.verified_numbers(account_id)
        return quote_time_state(balance, opted_out, sends_today, verified)

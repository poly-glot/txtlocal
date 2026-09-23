import asyncio
import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Protocol, assert_never

from txtlocal.shared.bus import Message, Queue
from txtlocal.shared.errors import BadRequest, Forbidden, Internal, NotFound, PaymentRequired
from txtlocal.shared.money import Micro, format_price
from txtlocal.shared.phone import normalise
from txtlocal.slices.billing.gateway import Card, Pack, PaymentEvent, ReturnUrls
from txtlocal.slices.billing.model import (
    Balance,
    BillingAccount,
    BillingSummary,
    Boost,
    CardView,
    CheckoutUrl,
    CreateTopUpRequest,
    GeneralSettings,
    GeneralUpdate,
    LedgerEntry,
    LedgerKind,
    LedgerOrder,
    PackagesView,
    Page,
    PowerPack,
    RechargeJob,
    TopUp,
    TopUpCreated,
    TopUpKind,
    TopUpStatus,
    TopUpStatusView,
    UpcomingCharge,
)
from txtlocal.slices.messaging.model import Product

if TYPE_CHECKING:
    from txtlocal.shared.bus import Bus
    from txtlocal.shared.clock import Clock
    from txtlocal.slices.billing.gateway import PaymentGateway
    from txtlocal.slices.billing.repo import BillingRepo

ONE_DAY = timedelta(days=1)
SAVINGS_PCT_SCALE = 100
TRIAL_CREDIT_MICRO = Micro(2_000_000)
TRIAL_LENGTH = timedelta(days=14)

MAX_CONTACT_NAME = 100
BALANCE_THRESHOLDS_MICRO = frozenset(
    {Micro(5_000_000), Micro(10_000_000), Micro(20_000_000), Micro(50_000_000)}
)
BALANCE_MANAGEMENT_FIELDS = frozenset(
    {
        "alert_threshold_micro",
        "auto_recharge",
        "low_balance_threshold_micro",
        "recharge_amount_micro",
    }
)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ACCOUNT_NOT_FOUND = "Account not found"
CARD_NOT_FOUND = "No saved card with that id"
CONTACTS_NOT_CONFIGURED = "billing contact reader not configured"
GATEWAY_NOT_CONFIGURED = "payment gateway not configured"
INSUFFICIENT_BALANCE = "Your balance is {balance}; this send costs {cost}"
INVALID_CONTACT_EMAIL = "Enter a valid email address"
INVALID_CONTACT_NAME = "Enter an account name of 1 to 100 characters"
LOW_BALANCE_ALERT_SUBJECT = "Your txtlocal balance is low"
NUMBERS_NOT_CONFIGURED = "dedicated numbers reader not configured"
RECHARGE_DECLINED_SUBJECT = "Your auto-recharge payment was declined"
TRIAL_ENDED = "Your free trial has ended. Top up to keep sending"
UNKNOWN_PACKAGE = "Choose a boost or a power pack from the list"


class ContactDetails(Protocol):
    @property
    def email(self) -> str: ...

    @property
    def mobile(self) -> str | None: ...

    @property
    def name(self) -> str: ...

    @property
    def pricing_country(self) -> str: ...


class AccountContacts(Protocol):
    async def contact_details(self, account_id: str) -> ContactDetails: ...

    async def update_contact_details(
        self, account_id: str, name: str, email: str, mobile: str | None
    ) -> ContactDetails: ...


class DueNumber(Protocol):
    @property
    def account_id(self) -> str: ...

    @property
    def monthly_price_micro(self) -> Micro: ...

    @property
    def renewal_attempt(self) -> int: ...

    @property
    def renews_at(self) -> datetime: ...

    @property
    def sender_id(self) -> str: ...

    @property
    def value(self) -> str: ...


class DedicatedNumbers(Protocol):
    async def due_for_renewal(self, now: datetime) -> Sequence[DueNumber]: ...

    async def rented_by(self, account_id: str) -> Sequence[DueNumber]: ...

    async def record_renewal(self, account_id: str, sender_id: str, now: datetime) -> None: ...

    async def record_renewal_attempt(
        self, account_id: str, sender_id: str, now: datetime
    ) -> None: ...

    async def release(self, account_id: str, sender_id: str) -> None: ...


class Email(Protocol):
    async def send(self, to: str, subject: str, body: str) -> None: ...


@dataclass(frozen=True, slots=True)
class BoostSpec:
    amount_micro: Micro
    code: str


@dataclass(frozen=True, slots=True)
class PackSpec:
    amount_micro: Micro
    code: str
    name: str
    rate_micro: Micro


@dataclass(frozen=True, slots=True)
class RechargeAccount:
    account_id: str
    amount_micro: Micro
    customer_id: str


BOOSTS: tuple[BoostSpec, ...] = (
    BoostSpec(amount_micro=Micro(10_000_000), code="BOOST_10"),
    BoostSpec(amount_micro=Micro(30_000_000), code="BOOST_30"),
    BoostSpec(amount_micro=Micro(50_000_000), code="BOOST_50"),
    BoostSpec(amount_micro=Micro(100_000_000), code="BOOST_100"),
)
RECHARGE_AMOUNTS_MICRO = frozenset(boost.amount_micro for boost in BOOSTS)
PACKS: tuple[PackSpec, ...] = (
    PackSpec(
        amount_micro=Micro(300_000_000), code="GROWTH", name="Growth pack", rate_micro=Micro(38_700)
    ),
    PackSpec(
        amount_micro=Micro(1_500_000_000), code="SCALE", name="Scale pack", rate_micro=Micro(34_300)
    ),
    PackSpec(
        amount_micro=Micro(4_000_000_000),
        code="ENTERPRISE",
        name="Enterprise pack",
        rate_micro=Micro(31_300),
    ),
)


def choices_text(amounts_micro: frozenset[Micro]) -> str:
    *leading, last = [format_price(amount) for amount in sorted(amounts_micro)]
    return f"{', '.join(leading)} or {last}"


INVALID_ALERT_THRESHOLD = f"Choose a balance alert of {choices_text(BALANCE_THRESHOLDS_MICRO)}"
INVALID_LOW_BALANCE_THRESHOLD = (
    f"Choose a recharge threshold of {choices_text(BALANCE_THRESHOLDS_MICRO)}"
)
INVALID_RECHARGE_AMOUNT = f"Choose a recharge amount of {choices_text(RECHARGE_AMOUNTS_MICRO)}"


def is_within_trial(trial_ends_at: datetime | None, now: datetime) -> bool:
    return trial_ends_at is not None and now < trial_ends_at


def can_send(account: BillingAccount, now: datetime) -> bool:
    return account.has_topped_up or is_within_trial(account.trial_ends_at, now)


def trial_days_left(trial_ends_at: datetime | None, now: datetime) -> int:
    if trial_ends_at is None:
        return 0
    return max(0, -((now - trial_ends_at) // ONE_DAY))


def insufficient_balance(balance_micro: Micro, cost_micro: Micro) -> str:
    return INSUFFICIENT_BALANCE.format(
        balance=format_price(balance_micro), cost=format_price(cost_micro)
    )


def crosses_below(before_micro: Micro, after_micro: Micro, threshold_micro: Micro) -> bool:
    return before_micro >= threshold_micro > after_micro


def low_balance_alert_body(threshold_micro: Micro) -> str:
    return (
        f"Your balance has dropped below {format_price(threshold_micro)}. "
        "Top up or turn on auto-recharge to keep sending."
    )


def recharge_declined_body(decline_code: str) -> str:
    return (
        f"We could not charge your card for auto-recharge ({decline_code}), so it has been "
        "turned off. Add a working card and turn auto-recharge back on to keep your balance "
        "topped up automatically."
    )


def balance_of(account: BillingAccount, now: datetime) -> Balance:
    return Balance(
        balance_micro=account.balance_micro,
        can_send=can_send(account, now),
        has_topped_up=account.has_topped_up,
        trial_days_left=trial_days_left(account.trial_ends_at, now),
        trial_ends_at=account.trial_ends_at,
    )


def summary_of(account: BillingAccount, now: datetime) -> BillingSummary:
    balance = balance_of(account, now)
    return BillingSummary(
        auto_recharge=account.auto_recharge,
        balance_micro=balance.balance_micro,
        can_send=balance.can_send,
        has_topped_up=balance.has_topped_up,
        low_balance_threshold_micro=account.low_balance_threshold_micro,
        recharge_amount_micro=account.recharge_amount_micro,
        trial_days_left=balance.trial_days_left,
        trial_ends_at=balance.trial_ends_at,
    )


def ledger_entry(
    kind: LedgerKind,
    amount_micro: Micro,
    balance_after_micro: Micro,
    now: datetime,
    ref: str | None = None,
) -> LedgerEntry:
    return LedgerEntry(
        amount_micro=amount_micro,
        balance_after_micro=balance_after_micro,
        created_at=now,
        entry_id=str(uuid.uuid7()),
        kind=kind,
        ref=ref,
    )


def estimate_of(credited_micro: Micro, base_rate_micro: Micro) -> int:
    return credited_micro // base_rate_micro


def pack_credited_micro(
    amount_micro: Micro, base_rate_micro: Micro, pack_rate_micro: Micro
) -> Micro:
    return Micro(amount_micro * base_rate_micro // pack_rate_micro)


def savings_pct(base_rate_micro: Micro, pack_rate_micro: Micro) -> int:
    return SAVINGS_PCT_SCALE * (base_rate_micro - pack_rate_micro) // base_rate_micro


def credited_micro_of(spec: BoostSpec | PackSpec, base_rate_micro: Micro) -> Micro:
    if isinstance(spec, PackSpec):
        return pack_credited_micro(spec.amount_micro, base_rate_micro, spec.rate_micro)
    return spec.amount_micro


def boost_view(spec: BoostSpec, base_rate_micro: Micro) -> Boost:
    return Boost(
        amount_micro=spec.amount_micro,
        code=spec.code,
        estimate=estimate_of(spec.amount_micro, base_rate_micro),
    )


def pack_view(spec: PackSpec, base_rate_micro: Micro) -> PowerPack:
    credited = pack_credited_micro(spec.amount_micro, base_rate_micro, spec.rate_micro)
    return PowerPack(
        amount_micro=spec.amount_micro,
        code=spec.code,
        credited_micro=credited,
        estimate=estimate_of(credited, base_rate_micro),
        name=spec.name,
        rate_micro=spec.rate_micro,
        savings_pct=savings_pct(base_rate_micro, spec.rate_micro),
    )


def find_package(kind: TopUpKind, code: str) -> BoostSpec | PackSpec:
    match kind:
        case TopUpKind.BOOST:
            found: BoostSpec | PackSpec | None = next((b for b in BOOSTS if b.code == code), None)
        case TopUpKind.PACK:
            found = next((p for p in PACKS if p.code == code), None)
        case _:
            assert_never(kind)
    if found is None:
        raise BadRequest(UNKNOWN_PACKAGE)
    return found


def package_name(spec: BoostSpec | PackSpec) -> str:
    return (
        spec.name
        if isinstance(spec, PackSpec)
        else f"Credit boost {format_price(spec.amount_micro)}"
    )


def card_view_of(card: Card) -> CardView:
    return CardView(
        brand=card.brand,
        cardholder_name=card.cardholder_name,
        exp_month=card.exp_month,
        exp_year=card.exp_year,
        is_default=card.is_default,
        last4=card.last4,
        payment_method_id=card.payment_method_id,
    )


def checked_contact_name(value: str) -> str:
    name = value.strip()
    if not (1 <= len(name) <= MAX_CONTACT_NAME):
        raise BadRequest(INVALID_CONTACT_NAME)
    return name


def checked_contact_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_PATTERN.match(email):
        raise BadRequest(INVALID_CONTACT_EMAIL)
    return email


def checked_choice(
    value: Micro | None, choices: frozenset[Micro], refusal: str, current: Micro
) -> Micro:
    if value is None or value == current:
        return current
    if value not in choices:
        raise BadRequest(refusal)
    return value


def checked_contact_mobile(value: str | None, default_country: str) -> str | None:
    raw = (value or "").strip()
    return normalise(raw, default_country) if raw else None


@dataclass(frozen=True, slots=True)
class BillingService:
    clock: Clock
    repo: BillingRepo
    bus: Bus | None = None
    contacts: AccountContacts | None = None
    email: Email | None = None
    gateway: PaymentGateway | None = None
    numbers: DedicatedNumbers | None = None
    public_base_url: str = ""

    async def open_account(self, account_id: str, now: datetime) -> None:
        entry = ledger_entry(LedgerKind.TRIAL, TRIAL_CREDIT_MICRO, TRIAL_CREDIT_MICRO, now)
        await self.repo.grant_trial(account_id, entry, now + TRIAL_LENGTH)

    async def rate(self, country: str, product: Product) -> Micro:
        price_micro = await self.repo.rate(country, product)
        if price_micro is None:
            raise Internal(f"no rate for {country} {product}")
        return price_micro

    async def balance(self, account_id: str, now: datetime) -> Balance:
        return balance_of(await self._account(account_id), now)

    async def summary(self, account_id: str) -> BillingSummary:
        return summary_of(await self._account(account_id), self.clock())

    async def reserve(self, account_id: str, amount_micro: Micro, ref: str, now: datetime) -> None:
        if amount_micro <= 0:
            raise Internal(f"reserve of {amount_micro} micro for {ref}")

        account = await self._account(account_id)
        if not can_send(account, now):
            raise Forbidden(TRIAL_ENDED)

        balance_after = Micro(account.balance_micro - amount_micro)
        entry = ledger_entry(LedgerKind.SEND, Micro(-amount_micro), balance_after, now, ref)
        if not await self.repo.debit(account_id, entry):
            raise PaymentRequired(insufficient_balance(account.balance_micro, amount_micro))

        await self._maybe_recharge(account_id, account, balance_after, now)
        await self._maybe_alert_low_balance(account_id, account, balance_after, now)

    async def settle(
        self,
        account_id: str,
        ref: str,
        reserved_micro: Micro,
        settled_micro: Micro,
        now: datetime,
    ) -> None:
        refund_micro = Micro(reserved_micro - settled_micro)
        if refund_micro <= 0:
            return

        account = await self._account(account_id)
        balance_after = Micro(account.balance_micro + refund_micro)
        entry = ledger_entry(LedgerKind.REFUND, refund_micro, balance_after, now, ref)
        await self.repo.credit(account_id, entry)

    async def charge_rental(
        self, account_id: str, sender_id: str, amount_micro: Micro, now: datetime, period: datetime
    ) -> None:
        account = await self._account(account_id)
        balance_after = Micro(account.balance_micro - amount_micro)
        entry = ledger_entry(LedgerKind.RENTAL, Micro(-amount_micro), balance_after, now, sender_id)

        if await self.repo.charge_rental_once(account_id, sender_id, period, entry):
            await self._maybe_recharge(account_id, account, balance_after, now)
            await self._maybe_alert_low_balance(account_id, account, balance_after, now)
            return

        if await self.repo.rental_charged(sender_id, period):
            return

        raise PaymentRequired(insufficient_balance(account.balance_micro, amount_micro))

    async def can_purchase(self, account_id: str, now: datetime) -> bool:
        return (await self.balance(account_id, now)).can_send

    async def charge_and_rent(
        self, account_id: str, sender_id: str, amount_micro: Micro, now: datetime
    ) -> None:
        await self.charge_rental(account_id, sender_id, amount_micro, now, now)

        account = await self._account(account_id)
        if not account.auto_recharge:
            await self.repo.update_balance_management(
                account_id,
                alert_threshold_micro=account.alert_threshold_micro,
                auto_recharge=True,
                low_balance_threshold_micro=account.low_balance_threshold_micro,
                recharge_amount_micro=account.recharge_amount_micro,
            )

    async def ledger(self, account_id: str, cursor: str | None) -> Page[LedgerEntry]:
        return await self.repo.ledger_page(account_id, cursor)

    async def transactions(
        self, account_id: str, cursor: str | None, order: LedgerOrder
    ) -> Page[LedgerEntry]:
        return await self.repo.topups_page(account_id, cursor, order)

    async def packages(self, country: str) -> PackagesView:
        base_rate = await self.rate(country, Product.SMS)
        return PackagesView(
            boosts=[boost_view(spec, base_rate) for spec in BOOSTS],
            packs=[pack_view(spec, base_rate) for spec in PACKS],
            rate_micro=base_rate,
        )

    async def create_top_up(
        self, account_id: str, request: CreateTopUpRequest, now: datetime
    ) -> TopUpCreated:
        contact = await self._contacts().contact_details(account_id)
        account = await self._account(account_id)
        base_rate = await self.rate(contact.pricing_country, Product.SMS)
        spec = find_package(request.kind, request.code)
        credited_micro = credited_micro_of(spec, base_rate)
        customer_id = await self._ensure_customer(account_id, account, contact)

        top_up_id = str(uuid.uuid7())
        top_up = TopUp(
            account_id=account_id,
            amount_micro=spec.amount_micro,
            code=spec.code,
            created_at=now,
            credited_micro=credited_micro,
            kind=request.kind,
            status=TopUpStatus.PENDING,
            top_up_id=top_up_id,
        )
        if not await self.repo.put_topup(top_up):
            raise Internal(f"top-up id collision {top_up_id}")

        urls = ReturnUrls(
            cancel_url=f"{self.public_base_url}/billing",
            success_url=f"{self.public_base_url}/billing?topup={top_up_id}",
        )
        pack = Pack(
            account_id=account_id,
            amount_micro=spec.amount_micro,
            code=spec.code,
            name=package_name(spec),
            top_up_id=top_up_id,
        )
        session = await self._gateway().checkout(customer_id, pack, urls, top_up_id)
        return TopUpCreated(checkout_url=session.url, top_up_id=top_up_id)

    async def top_up_status(self, account_id: str, top_up_id: str) -> TopUpStatusView:
        top_up = await self.repo.get_topup(account_id, top_up_id)
        if top_up is None:
            raise NotFound(f"top-up {top_up_id} not found")
        credited = top_up.credited_micro if top_up.status is TopUpStatus.PAID else None
        return TopUpStatusView(credited_micro=credited, status=top_up.status)

    async def credit_top_up(self, event: PaymentEvent, now: datetime) -> None:
        if event.account_id is None or event.top_up_id is None:
            raise Internal(f"checkout.session.completed event {event.event_id} is missing metadata")

        top_up = await self.repo.get_topup(event.account_id, event.top_up_id)
        if top_up is None:
            raise Internal(f"top-up {event.top_up_id} not found for account {event.account_id}")

        account = await self._account(event.account_id)
        balance_after = Micro(account.balance_micro + top_up.credited_micro)
        entry = ledger_entry(
            LedgerKind.TOPUP, top_up.credited_micro, balance_after, now, ref=top_up.top_up_id
        ).model_copy(
            update={
                "credited_micro": top_up.credited_micro,
                "paid_micro": top_up.amount_micro,
                "stripe_invoice_number": event.invoice_number,
                "stripe_invoice_url": event.invoice_url,
            }
        )
        paid_top_up = top_up.model_copy(
            update={
                "invoice_number": event.invoice_number,
                "invoice_url": event.invoice_url,
                "status": TopUpStatus.PAID,
            }
        )
        if not await self.repo.credit_topup(event.event_id, paid_top_up, entry):
            return
        await self._maybe_clear_low_balance_alert(event.account_id, account, balance_after)

    async def cards(self, account_id: str) -> list[CardView]:
        account = await self._account(account_id)
        if account.stripe_customer_id is None:
            return []
        cards = await self._gateway().payment_methods(account.stripe_customer_id)
        return [card_view_of(card) for card in cards]

    async def add_card(self, account_id: str) -> CheckoutUrl:
        contact = await self._contacts().contact_details(account_id)
        account = await self._account(account_id)
        customer_id = await self._ensure_customer(account_id, account, contact)

        urls = ReturnUrls(
            cancel_url=f"{self.public_base_url}/billing",
            success_url=f"{self.public_base_url}/billing",
        )
        session = await self._gateway().setup_session(customer_id, urls)
        return CheckoutUrl(checkout_url=session.url)

    async def set_default_card(self, account_id: str, payment_method_id: str) -> None:
        customer_id = await self._owned_customer(account_id, payment_method_id)
        await self._gateway().set_default(customer_id, payment_method_id)

    async def remove_card(self, account_id: str, payment_method_id: str) -> None:
        await self._owned_customer(account_id, payment_method_id)
        await self._gateway().detach(payment_method_id)

    async def general(self, account_id: str) -> GeneralSettings:
        account, contact = await asyncio.gather(
            self._account(account_id), self._contacts().contact_details(account_id)
        )
        return general_settings_of(account, contact)

    async def update_general(self, account_id: str, update: GeneralUpdate) -> GeneralSettings:
        account = await self._account(account_id)
        contacts = self._contacts()
        contact = await contacts.contact_details(account_id)

        if {"email", "mobile", "name"} & update.model_fields_set:
            name = checked_contact_name(update.name) if update.name is not None else contact.name
            email = (
                checked_contact_email(update.email) if update.email is not None else contact.email
            )
            mobile = (
                checked_contact_mobile(update.mobile, contact.pricing_country)
                if "mobile" in update.model_fields_set
                else contact.mobile
            )
            contact = await contacts.update_contact_details(account_id, name, email, mobile)

        if BALANCE_MANAGEMENT_FIELDS & update.model_fields_set:
            account = await self._update_balance_management(account_id, account, update)

        return general_settings_of(account, contact)

    async def _update_balance_management(
        self, account_id: str, account: BillingAccount, update: GeneralUpdate
    ) -> BillingAccount:
        alert_threshold = checked_choice(
            update.alert_threshold_micro,
            BALANCE_THRESHOLDS_MICRO,
            INVALID_ALERT_THRESHOLD,
            account.alert_threshold_micro,
        )
        auto_recharge = (
            update.auto_recharge if update.auto_recharge is not None else account.auto_recharge
        )
        low_balance_threshold = checked_choice(
            update.low_balance_threshold_micro,
            BALANCE_THRESHOLDS_MICRO,
            INVALID_LOW_BALANCE_THRESHOLD,
            account.low_balance_threshold_micro,
        )
        recharge_amount = checked_choice(
            update.recharge_amount_micro,
            RECHARGE_AMOUNTS_MICRO,
            INVALID_RECHARGE_AMOUNT,
            account.recharge_amount_micro,
        )

        if not await self.repo.update_balance_management(
            account_id,
            alert_threshold_micro=alert_threshold,
            auto_recharge=auto_recharge,
            low_balance_threshold_micro=low_balance_threshold,
            recharge_amount_micro=recharge_amount,
        ):
            raise Internal("account missing")

        return account.model_copy(
            update={
                "alert_threshold_micro": alert_threshold,
                "auto_recharge": auto_recharge,
                "low_balance_threshold_micro": low_balance_threshold,
                "recharge_amount_micro": recharge_amount,
            }
        )

    async def upcoming_charges(self, account_id: str) -> list[UpcomingCharge]:
        due = await self._numbers().rented_by(account_id)
        return [
            UpcomingCharge(
                monthly_price_micro=number.monthly_price_micro,
                renews_at=number.renews_at,
                value=number.value,
            )
            for number in due
        ]

    async def recharge_account(self, account_id: str) -> RechargeAccount | None:
        account = await self._account(account_id)
        if account.stripe_customer_id is None or not account.auto_recharge:
            return None
        return RechargeAccount(
            account_id=account_id,
            amount_micro=account.recharge_amount_micro,
            customer_id=account.stripe_customer_id,
        )

    async def credit_recharge(
        self, account_id: str, amount_micro: Micro, provider_ref: str, now: datetime
    ) -> None:
        account = await self._account(account_id)
        balance_after = Micro(account.balance_micro + amount_micro)
        entry = ledger_entry(
            LedgerKind.TOPUP, amount_micro, balance_after, now, ref=provider_ref
        ).model_copy(update={"credited_micro": amount_micro, "paid_micro": amount_micro})
        if not await self.repo.credit_recharge(provider_ref, account_id, entry):
            return
        await self._maybe_clear_low_balance_alert(account_id, account, balance_after)

    async def abandon_recharge(self, account_id: str) -> None:
        await self.repo.clear_recharge_in_flight(account_id)

    async def decline_recharge(
        self, idempotency_key: str, account_id: str, decline_code: str, now: datetime
    ) -> None:
        account = await self._account(account_id)
        entry = ledger_entry(
            LedgerKind.ADJUSTMENT, Micro(0), account.balance_micro, now, ref=decline_code
        )
        if not await self.repo.decline_recharge(idempotency_key, account_id, entry):
            return
        await self._alert_recharge_declined(account_id, decline_code)

    async def request_recharge(self, account_id: str, now: datetime) -> None:
        account = await self._account(account_id)
        if account.auto_recharge:
            await self._enqueue_recharge(account_id, now)

    async def _maybe_recharge(
        self, account_id: str, account: BillingAccount, balance_after: Micro, now: datetime
    ) -> None:
        if not account.auto_recharge or balance_after >= account.low_balance_threshold_micro:
            return
        await self._enqueue_recharge(account_id, now)

    async def _maybe_alert_low_balance(
        self, account_id: str, account: BillingAccount, balance_after: Micro, now: datetime
    ) -> None:
        email = self.email
        contacts = self.contacts
        if email is None or contacts is None:
            return
        if not crosses_below(account.balance_micro, balance_after, account.alert_threshold_micro):
            return
        if not await self.repo.set_low_balance_alerted(account_id, now):
            return

        contact = await contacts.contact_details(account_id)
        await email.send(
            to=contact.email,
            subject=LOW_BALANCE_ALERT_SUBJECT,
            body=low_balance_alert_body(account.alert_threshold_micro),
        )

    async def _maybe_clear_low_balance_alert(
        self, account_id: str, account: BillingAccount, balance_after: Micro
    ) -> None:
        if account.low_balance_alerted_at is None:
            return
        if balance_after < account.alert_threshold_micro:
            return
        await self.repo.clear_low_balance_alert(account_id)

    async def _alert_recharge_declined(self, account_id: str, decline_code: str) -> None:
        email = self.email
        contacts = self.contacts
        if email is None or contacts is None:
            return

        contact = await contacts.contact_details(account_id)
        await email.send(
            to=contact.email,
            subject=RECHARGE_DECLINED_SUBJECT,
            body=recharge_declined_body(decline_code),
        )

    async def _enqueue_recharge(self, account_id: str, now: datetime) -> None:
        if self.bus is None:
            return
        if await self.repo.set_recharge_in_flight(account_id, now):
            job = RechargeJob(account_id=account_id, job_id=str(uuid.uuid7()))
            await self.bus.send(Queue.RECHARGE, [Message(body=job.model_dump_json(by_alias=True))])

    async def _ensure_customer(
        self, account_id: str, account: BillingAccount, contact: ContactDetails
    ) -> str:
        if account.stripe_customer_id is not None:
            return account.stripe_customer_id
        customer_id = await self._gateway().ensure_customer(account_id, contact.email)
        await self.repo.save_stripe_customer_id(account_id, customer_id)
        return customer_id

    async def _owned_customer(self, account_id: str, payment_method_id: str) -> str:
        account = await self._account(account_id)
        if account.stripe_customer_id is None:
            raise NotFound(CARD_NOT_FOUND)
        cards = await self._gateway().payment_methods(account.stripe_customer_id)
        if not any(card.payment_method_id == payment_method_id for card in cards):
            raise NotFound(CARD_NOT_FOUND)
        return account.stripe_customer_id

    async def _account(self, account_id: str) -> BillingAccount:
        account = await self.repo.load_account(account_id)
        if account is None:
            raise NotFound(ACCOUNT_NOT_FOUND)
        return account

    def _gateway(self) -> PaymentGateway:
        if self.gateway is None:
            raise Internal(GATEWAY_NOT_CONFIGURED)
        return self.gateway

    def _contacts(self) -> AccountContacts:
        if self.contacts is None:
            raise Internal(CONTACTS_NOT_CONFIGURED)
        return self.contacts

    def _numbers(self) -> DedicatedNumbers:
        if self.numbers is None:
            raise Internal(NUMBERS_NOT_CONFIGURED)
        return self.numbers


def general_settings_of(account: BillingAccount, contact: ContactDetails) -> GeneralSettings:
    return GeneralSettings(
        alert_threshold_micro=account.alert_threshold_micro,
        auto_recharge=account.auto_recharge,
        email=contact.email,
        low_balance_threshold_micro=account.low_balance_threshold_micro,
        mobile=contact.mobile,
        name=contact.name,
        recharge_amount_micro=account.recharge_amount_micro,
    )

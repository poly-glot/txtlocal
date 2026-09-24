import json
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID, uuid7

from txtlocal.shared.errors import BadRequest, NotFound
from txtlocal.shared.money import Micro
from txtlocal.shared.testing import RecordingBus
from txtlocal.slices.billing.gateway import (
    INVALID_SIGNATURE,
    NO_DEFAULT_CARD,
    Card,
    ChargeOutcome,
    ChargeStatus,
    CheckoutSession,
    Invoice,
    OffSessionCharge,
    Pack,
    PaymentEvent,
    PaymentGateway,
    ReturnUrls,
    as_mapping,
    payment_event_of,
    signature_fields,
)
from txtlocal.slices.billing.model import (
    BillingAccount,
    LedgerEntry,
    LedgerKind,
    LedgerOrder,
    Page,
    TopUp,
)
from txtlocal.slices.billing.repo import (
    EPOCH,
    PAGE_SIZE,
    RECHARGE_IN_FLIGHT_TTL,
    ledger_sort_key,
    rental_event_id,
)
from txtlocal.slices.billing.service import CARD_NOT_FOUND, AccountContacts, BillingService, Email

if TYPE_CHECKING:
    from txtlocal.slices.messaging.model import Product

ACCOUNT_ID = "account-under-test"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
ONE_MS = timedelta(milliseconds=1)
UUID7_VARIANT_BITS = 2 << 62
UUID7_VERSION_BITS = 7 << 76
ZERO = Micro(0)


def uuid7_at(moment: datetime) -> str:
    unix_ts_ms = (moment - EPOCH) // ONE_MS
    return str(UUID(int=(unix_ts_ms << 80) | UUID7_VERSION_BITS | UUID7_VARIANT_BITS))


class InMemoryBillingRepo:
    def __init__(self) -> None:
        self.accounts: dict[str, BillingAccount] = {}
        self.events: set[str] = set()
        self.ledgers: dict[str, dict[str, LedgerEntry]] = {}
        self.rates: dict[tuple[str, Product], Micro] = {}
        self.topups: dict[tuple[str, str], TopUp] = {}

    async def credit(self, account_id: str, entry: LedgerEntry) -> bool:
        account = self.accounts.get(account_id)
        if account is None or not self._append(account_id, entry):
            return False
        self._set_balance(account_id, Micro(account.balance_micro + entry.amount_micro))
        return True

    async def debit(self, account_id: str, entry: LedgerEntry) -> bool:
        account = self.accounts.get(account_id)
        cost = -entry.amount_micro
        if account is None or account.balance_micro < cost or not self._append(account_id, entry):
            return False
        self._set_balance(account_id, Micro(account.balance_micro - cost))
        return True

    async def charge_rental_once(
        self, account_id: str, sender_id: str, period: datetime, entry: LedgerEntry
    ) -> bool:
        account = self.accounts.get(account_id)
        event_id = rental_event_id(sender_id, period)
        cost = -entry.amount_micro
        if (
            account is None
            or event_id in self.events
            or account.balance_micro < cost
            or not self._append(account_id, entry)
        ):
            return False
        self.events.add(event_id)
        self._set_balance(account_id, Micro(account.balance_micro - cost))
        return True

    async def rental_charged(self, sender_id: str, period: datetime) -> bool:
        return rental_event_id(sender_id, period) in self.events

    async def grant_trial(
        self, account_id: str, entry: LedgerEntry, trial_ends_at: datetime
    ) -> bool:
        account = self.accounts.get(account_id)
        if account is None or not self._append(account_id, entry):
            return False
        self.accounts[account_id] = account.model_copy(
            update={
                "balance_micro": Micro(account.balance_micro + entry.amount_micro),
                "trial_ends_at": trial_ends_at,
            }
        )
        return True

    async def save_stripe_customer_id(self, account_id: str, customer_id: str) -> bool:
        account = self.accounts.get(account_id)
        if account is None or account.stripe_customer_id is not None:
            return False
        self.accounts[account_id] = account.model_copy(update={"stripe_customer_id": customer_id})
        return True

    async def set_recharge_in_flight(self, account_id: str, now: datetime) -> bool:
        account = self.accounts.get(account_id)
        if account is None:
            return False

        in_flight = account.recharge_in_flight
        if in_flight is not None and in_flight >= now - RECHARGE_IN_FLIGHT_TTL:
            return False

        self.accounts[account_id] = account.model_copy(update={"recharge_in_flight": now})
        return True

    async def clear_recharge_in_flight(self, account_id: str) -> bool:
        account = self.accounts.get(account_id)
        if account is None or account.recharge_in_flight is None:
            return False
        self.accounts[account_id] = account.model_copy(update={"recharge_in_flight": None})
        return True

    async def set_low_balance_alerted(self, account_id: str, now: datetime) -> bool:
        account = self.accounts.get(account_id)
        if account is None or account.low_balance_alerted_at is not None:
            return False
        self.accounts[account_id] = account.model_copy(update={"low_balance_alerted_at": now})
        return True

    async def clear_low_balance_alert(self, account_id: str) -> bool:
        account = self.accounts.get(account_id)
        if account is None or account.low_balance_alerted_at is None:
            return False
        self.accounts[account_id] = account.model_copy(update={"low_balance_alerted_at": None})
        return True

    async def update_balance_management(
        self,
        account_id: str,
        alert_threshold_micro: Micro,
        auto_recharge: bool,
        low_balance_threshold_micro: Micro,
        recharge_amount_micro: Micro,
    ) -> bool:
        account = self.accounts.get(account_id)
        if account is None:
            return False
        self.accounts[account_id] = account.model_copy(
            update={
                "alert_threshold_micro": alert_threshold_micro,
                "auto_recharge": auto_recharge,
                "low_balance_threshold_micro": low_balance_threshold_micro,
                "recharge_amount_micro": recharge_amount_micro,
            }
        )
        return True

    async def put_topup(self, top_up: TopUp) -> bool:
        top_up_key = (top_up.account_id, top_up.top_up_id)
        if top_up_key in self.topups:
            return False
        self.topups[top_up_key] = top_up
        return True

    async def get_topup(self, account_id: str, top_up_id: str) -> TopUp | None:
        return self.topups.get((account_id, top_up_id))

    async def credit_topup(self, event_id: str, top_up: TopUp, entry: LedgerEntry) -> bool:
        account = self.accounts.get(top_up.account_id)
        top_up_key = (top_up.account_id, top_up.top_up_id)
        if (
            account is None
            or top_up_key not in self.topups
            or event_id in self.events
            or not self._append(top_up.account_id, entry)
        ):
            return False
        self.events.add(event_id)
        self.accounts[top_up.account_id] = account.model_copy(
            update={
                "balance_micro": Micro(account.balance_micro + entry.amount_micro),
                "has_topped_up": True,
            }
        )
        self.topups[top_up_key] = top_up
        return True

    async def credit_recharge(
        self, idempotency_key: str, account_id: str, entry: LedgerEntry
    ) -> bool:
        account = self.accounts.get(account_id)
        if account is None or idempotency_key in self.events or not self._append(account_id, entry):
            return False
        self.events.add(idempotency_key)
        self.accounts[account_id] = account.model_copy(
            update={
                "balance_micro": Micro(account.balance_micro + entry.amount_micro),
                "has_topped_up": True,
                "recharge_in_flight": None,
            }
        )
        return True

    async def decline_recharge(
        self, idempotency_key: str, account_id: str, entry: LedgerEntry
    ) -> bool:
        account = self.accounts.get(account_id)
        if account is None or idempotency_key in self.events or not self._append(account_id, entry):
            return False
        self.events.add(idempotency_key)
        self.accounts[account_id] = account.model_copy(
            update={"auto_recharge": False, "recharge_in_flight": None}
        )
        return True

    async def ledger_page(self, account_id: str, cursor: str | None) -> Page[LedgerEntry]:
        return self._page(account_id, cursor, None, LedgerOrder.DESC)

    async def topups_page(
        self, account_id: str, cursor: str | None, order: LedgerOrder
    ) -> Page[LedgerEntry]:
        return self._page(account_id, cursor, LedgerKind.TOPUP, order)

    async def load_account(self, account_id: str) -> BillingAccount | None:
        return self.accounts.get(account_id)

    async def rate(self, country: str, product: Product) -> Micro | None:
        return self.rates.get((country, product))

    def _page(
        self, account_id: str, cursor: str | None, kind: LedgerKind | None, order: LedgerOrder
    ) -> Page[LedgerEntry]:
        rows = self.ledgers.get(account_id, {})
        descending = order is LedgerOrder.DESC
        keys = sorted(
            (
                k
                for k, entry in rows.items()
                if (cursor is None or (k < cursor if descending else k > cursor))
                and (kind is None or entry.kind is kind)
            ),
            reverse=descending,
        )
        page = keys[:PAGE_SIZE]
        return Page[LedgerEntry](
            items=[rows[k] for k in page],
            next_cursor=page[-1] if len(keys) > PAGE_SIZE else None,
        )

    def _append(self, account_id: str, entry: LedgerEntry) -> bool:
        rows = self.ledgers.setdefault(account_id, {})
        sort_key = ledger_sort_key(entry)
        if sort_key in rows:
            return False
        rows[sort_key] = entry
        return True

    def _set_balance(self, account_id: str, balance_micro: Micro) -> None:
        self.accounts[account_id] = self.accounts[account_id].model_copy(
            update={"balance_micro": balance_micro}
        )


def account_row(repo: InMemoryBillingRepo, **overrides: object) -> None:
    account = BillingAccount(balance_micro=ZERO, has_topped_up=False)
    repo.accounts[ACCOUNT_ID] = account.model_copy(update=overrides) if overrides else account


def ledger_of(repo: InMemoryBillingRepo) -> list[LedgerEntry]:
    rows = repo.ledgers.get(ACCOUNT_ID, {})
    return [rows[k] for k in sorted(rows, reverse=True)]


def billing(repo: InMemoryBillingRepo, now: datetime = NOW) -> BillingService:
    return BillingService(bus=RecordingBus(), clock=lambda: now, public_base_url="", repo=repo)


@dataclass(frozen=True, slots=True)
class FakeContact:
    email: str
    mobile: str | None
    name: str
    pricing_country: str = "GB"


@dataclass(slots=True)
class FakeContacts:
    contact: FakeContact
    reads: list[str] = field(default_factory=list)
    updates: list[tuple[str, str, str, str | None]] = field(default_factory=list)

    async def contact_details(self, account_id: str) -> FakeContact:
        self.reads.append(account_id)
        return self.contact

    async def update_contact_details(
        self, account_id: str, name: str, email: str, mobile: str | None
    ) -> FakeContact:
        self.updates.append((account_id, name, email, mobile))
        self.contact = FakeContact(
            email=email, mobile=mobile, name=name, pricing_country=self.contact.pricing_country
        )
        return self.contact


def _fits_contacts(fake: FakeContacts) -> AccountContacts:
    return fake


@dataclass
class RecordingEmail:
    sent: list[tuple[str, str, str]] = field(default_factory=list)

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


def _fits_email(fake: RecordingEmail) -> Email:
    return fake


CHECKOUT_URL = "https://checkout.stripe.com/c/pay/"
INVOICE_URL = "https://invoice.stripe.com/i/"
SEED_VISA = Card(
    brand="visa",
    cardholder_name="Demo Card",
    exp_month=12,
    exp_year=2035,
    last4="4242",
    payment_method_id="pm_demo_4242",
)
SEED_DECLINING = replace(SEED_VISA, last4="0002", payment_method_id="pm_demo_0002")


@dataclass(slots=True)
class StoredCustomer:
    cards: dict[str, Card] = field(default_factory=dict)
    default: str | None = None


@dataclass(frozen=True, slots=True)
class FakePaymentGateway:
    customers: dict[str, StoredCustomer] = field(default_factory=dict)

    async def ensure_customer(self, _account_id: str, _email: str) -> str:
        customer_id = f"cus_demo_{uuid7()}"
        self.customers[customer_id] = StoredCustomer(
            cards={
                SEED_VISA.payment_method_id: SEED_VISA,
                SEED_DECLINING.payment_method_id: SEED_DECLINING,
            },
            default=SEED_VISA.payment_method_id,
        )
        return customer_id

    async def checkout(
        self, _customer_id: str, _pack: Pack, _urls: ReturnUrls, _idempotency_key: str
    ) -> CheckoutSession:
        return self._session()

    async def setup_session(self, _customer_id: str, _urls: ReturnUrls) -> CheckoutSession:
        return self._session()

    async def payment_methods(self, customer_id: str) -> list[Card]:
        stored = self.customers.get(customer_id)
        if stored is None:
            return []
        return [
            replace(card, is_default=pm_id == stored.default)
            for pm_id, card in stored.cards.items()
        ]

    async def set_default(self, customer_id: str, payment_method_id: str) -> None:
        stored = self.customers.get(customer_id)
        if stored is None or payment_method_id not in stored.cards:
            raise NotFound(CARD_NOT_FOUND)
        stored.default = payment_method_id

    async def detach(self, payment_method_id: str) -> None:
        for stored in self.customers.values():
            if payment_method_id in stored.cards:
                del stored.cards[payment_method_id]
                if stored.default == payment_method_id:
                    stored.default = None
                return
        raise NotFound(CARD_NOT_FOUND)

    async def charge_off_session(self, charge: OffSessionCharge) -> ChargeOutcome:
        stored = self.customers.get(charge.customer_id)
        default_id = stored.default if stored is not None else None
        if default_id is None:
            return ChargeOutcome(status=ChargeStatus.DECLINED, decline_code=NO_DEFAULT_CARD)
        if default_id == SEED_DECLINING.payment_method_id:
            return ChargeOutcome(status=ChargeStatus.DECLINED, decline_code="card_declined")
        return ChargeOutcome(
            status=ChargeStatus.SUCCEEDED, provider_ref=f"pi_demo_{charge.idempotency_key}"
        )

    async def invoice(self, invoice_id: str) -> Invoice:
        return Invoice(
            number=f"INV-{invoice_id.removeprefix('in_')}", url=f"{INVOICE_URL}{invoice_id}"
        )

    def verify_webhook(self, payload: bytes, signature: str, _now: datetime) -> PaymentEvent:
        values = [value for name, value in signature_fields(signature) if name == "v1"]
        if values != ["fake"]:
            raise BadRequest(INVALID_SIGNATURE)
        return payment_event_of(as_mapping(json.loads(payload)))

    def _session(self) -> CheckoutSession:
        session_id = f"cs_demo_{uuid7()}"
        return CheckoutSession(session_id=session_id, url=f"{CHECKOUT_URL}{session_id}")


def _fits_gateway(fake: FakePaymentGateway) -> PaymentGateway:
    return fake

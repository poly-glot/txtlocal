from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from txtlocal.shared.model import Model
from txtlocal.shared.money import Micro

DEFAULT_ALERT_THRESHOLD_MICRO = Micro(5_000_000)
DEFAULT_LOW_BALANCE_THRESHOLD_MICRO = Micro(5_000_000)
DEFAULT_RECHARGE_AMOUNT_MICRO = Micro(10_000_000)


class LedgerKind(StrEnum):
    ADJUSTMENT = "ADJUSTMENT"
    REFUND = "REFUND"
    RENTAL = "RENTAL"
    SEND = "SEND"
    TOPUP = "TOPUP"
    TRIAL = "TRIAL"


class LedgerOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class TopUpKind(StrEnum):
    BOOST = "BOOST"
    PACK = "PACK"


class TopUpStatus(StrEnum):
    EXPIRED = "EXPIRED"
    PAID = "PAID"
    PENDING = "PENDING"


@dataclass(frozen=True, slots=True)
class Balance:
    balance_micro: Micro
    can_send: bool
    has_topped_up: bool
    trial_days_left: int
    trial_ends_at: datetime | None


class BillingAccount(Model):
    alert_threshold_micro: Micro = DEFAULT_ALERT_THRESHOLD_MICRO
    auto_recharge: bool = False
    balance_micro: Micro
    has_topped_up: bool
    low_balance_alerted_at: datetime | None = None
    low_balance_threshold_micro: Micro = DEFAULT_LOW_BALANCE_THRESHOLD_MICRO
    recharge_amount_micro: Micro = DEFAULT_RECHARGE_AMOUNT_MICRO
    recharge_in_flight: datetime | None = None
    stripe_customer_id: str | None = None
    trial_ends_at: datetime | None = None


class LedgerEntry(Model):
    amount_micro: Micro
    balance_after_micro: Micro
    created_at: datetime
    credited_micro: Micro | None = None
    entry_id: str
    kind: LedgerKind
    paid_micro: Micro | None = None
    ref: str | None = None
    stripe_invoice_number: str | None = None
    stripe_invoice_url: str | None = None


class BillingSummary(Model):
    auto_recharge: bool
    balance_micro: Micro
    can_send: bool
    has_topped_up: bool
    low_balance_threshold_micro: Micro
    recharge_amount_micro: Micro
    trial_days_left: int
    trial_ends_at: datetime | None


class Page[T](Model):
    items: list[T]
    next_cursor: str | None = None


class TopUp(Model):
    account_id: str
    amount_micro: Micro
    code: str
    created_at: datetime
    credited_micro: Micro
    invoice_number: str | None = None
    invoice_url: str | None = None
    kind: TopUpKind
    status: TopUpStatus
    top_up_id: str


class CreateTopUpRequest(Model):
    code: str
    kind: TopUpKind


class TopUpCreated(Model):
    checkout_url: str
    top_up_id: str


class TopUpStatusView(Model):
    credited_micro: Micro | None = None
    status: TopUpStatus


class Boost(Model):
    amount_micro: Micro
    code: str
    estimate: int


class PowerPack(Model):
    amount_micro: Micro
    code: str
    credited_micro: Micro
    estimate: int
    name: str
    rate_micro: Micro
    savings_pct: int


class PackagesView(Model):
    boosts: list[Boost]
    packs: list[PowerPack]
    rate_micro: Micro


class CardView(Model):
    brand: str
    cardholder_name: str
    exp_month: int
    exp_year: int
    is_default: bool
    last4: str
    payment_method_id: str


class CheckoutUrl(Model):
    checkout_url: str


class GeneralSettings(Model):
    alert_threshold_micro: Micro
    auto_recharge: bool
    email: str
    low_balance_threshold_micro: Micro
    mobile: str | None
    name: str
    recharge_amount_micro: Micro


class GeneralUpdate(Model):
    alert_threshold_micro: Micro | None = None
    auto_recharge: bool | None = None
    email: str | None = None
    low_balance_threshold_micro: Micro | None = None
    mobile: str | None = None
    name: str | None = None
    recharge_amount_micro: Micro | None = None


class UpcomingCharge(Model):
    monthly_price_micro: Micro
    renews_at: datetime
    value: str


class RechargeJob(Model):
    account_id: str
    job_id: str

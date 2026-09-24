from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from txtlocal.entrypoints.billing_charge import (
    Billing,
    BillingCharge,
    Charger,
    RechargeAccount,
    idempotency_key_of,
)
from txtlocal.shared.errors import Internal
from txtlocal.shared.money import Micro
from txtlocal.slices.billing.gateway import ChargeOutcome, ChargeStatus, OffSessionCharge
from txtlocal.slices.billing.model import RechargeJob
from txtlocal.slices.billing.tests.fakes import SEED_DECLINING, FakePaymentGateway

if TYPE_CHECKING:
    from txtlocal.shared.bus import SqsEvent

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
LATER = datetime(2026, 9, 19, 13, 0, tzinfo=UTC)
ACCOUNT_ID = "acc-1"
JOB_ID = "job-1"


@dataclass(frozen=True, slots=True)
class FakeRechargeAccount:
    account_id: str
    amount_micro: Micro
    customer_id: str


@dataclass(slots=True)
class FakeBilling:
    account: FakeRechargeAccount | None
    fail_for: frozenset[str] = frozenset()
    abandoned: list[str] = field(default_factory=list)
    credited: list[tuple[str, Micro, str]] = field(default_factory=list)
    declined: list[tuple[str, str, str]] = field(default_factory=list)

    async def recharge_account(self, account_id: str) -> FakeRechargeAccount | None:
        if account_id in self.fail_for:
            raise Internal("boom")
        return self.account

    async def abandon_recharge(self, account_id: str) -> None:
        self.abandoned.append(account_id)

    async def credit_recharge(
        self, account_id: str, amount_micro: Micro, provider_ref: str, _now: datetime
    ) -> None:
        self.credited.append((account_id, amount_micro, provider_ref))

    async def decline_recharge(
        self, idempotency_key: str, account_id: str, decline_code: str, _now: datetime
    ) -> None:
        self.declined.append((idempotency_key, account_id, decline_code))


@dataclass(frozen=True, slots=True)
class ErroringCharger:
    async def charge_off_session(self, _charge: OffSessionCharge) -> ChargeOutcome:
        return ChargeOutcome(status=ChargeStatus.ERRORED, decline_code="api_error")


@dataclass(slots=True)
class PendingCharger:
    charges: list[OffSessionCharge] = field(default_factory=list)

    async def charge_off_session(self, charge: OffSessionCharge) -> ChargeOutcome:
        self.charges.append(charge)
        return ChargeOutcome(status=ChargeStatus.PENDING, provider_ref="pi_1")


def _fits(fake: FakeBilling) -> Billing:
    return fake


def _fits_account(fake: FakeRechargeAccount) -> RechargeAccount:
    return fake


def _fits_charger(fake: ErroringCharger | PendingCharger) -> Charger:
    return fake


async def gateway_with_customer() -> tuple[FakePaymentGateway, str]:
    gateway = FakePaymentGateway()
    customer_id = await gateway.ensure_customer(ACCOUNT_ID, "a@b.example")
    return gateway, customer_id


def charge_over(billing: FakeBilling, gateway: Charger, now: datetime = NOW) -> BillingCharge:
    return BillingCharge(billing=billing, clock=lambda: now, gateway=gateway)


def job_body(account_id: str = ACCOUNT_ID, job_id: str = JOB_ID) -> str:
    return RechargeJob(account_id=account_id, job_id=job_id).model_dump_json()


def billing_for(customer_id: str) -> FakeBilling:
    return FakeBilling(
        FakeRechargeAccount(
            account_id=ACCOUNT_ID, amount_micro=Micro(10_000_000), customer_id=customer_id
        )
    )


async def test_handle_body_credits_a_covered_account() -> None:
    gateway, customer_id = await gateway_with_customer()
    billing = billing_for(customer_id)

    await charge_over(billing, gateway).handle_body(job_body())

    assert billing.declined == []
    assert [(row[0], row[1]) for row in billing.credited] == [(ACCOUNT_ID, 10_000_000)]


async def test_idempotency_key_is_the_jobs_own_id() -> None:
    assert idempotency_key_of(RechargeJob(account_id=ACCOUNT_ID, job_id=JOB_ID)) == "recharge_job-1"


async def test_handle_body_retried_an_hour_later_charges_under_the_same_key() -> None:
    gateway, customer_id = await gateway_with_customer()
    billing = billing_for(customer_id)

    await charge_over(billing, gateway).handle_body(job_body())
    await charge_over(billing, gateway, LATER).handle_body(job_body())

    assert [row[2] for row in billing.credited] == ["pi_demo_recharge_job-1"] * 2


async def test_handle_body_declines_a_customer_whose_default_card_always_declines() -> None:
    gateway, customer_id = await gateway_with_customer()
    await gateway.set_default(customer_id, SEED_DECLINING.payment_method_id)
    billing = billing_for(customer_id)

    await charge_over(billing, gateway).handle_body(job_body())

    assert billing.credited == []
    assert [row[1] for row in billing.declined] == [ACCOUNT_ID]


async def test_handle_body_skips_an_account_no_longer_eligible() -> None:
    gateway, _ = await gateway_with_customer()
    billing = FakeBilling(None)

    await charge_over(billing, gateway).handle_body(job_body())

    assert billing.credited == []
    assert billing.declined == []


async def test_handle_body_clears_the_flight_flag_of_an_account_no_longer_eligible() -> None:
    gateway, _ = await gateway_with_customer()
    billing = FakeBilling(None)

    await charge_over(billing, gateway).handle_body(job_body())

    assert billing.abandoned == [ACCOUNT_ID]


async def test_handle_body_clears_the_flight_flag_when_the_charge_errors() -> None:
    billing = billing_for("cus_1")

    await charge_over(billing, ErroringCharger()).handle_body(job_body())

    assert billing.abandoned == [ACCOUNT_ID]
    assert billing.credited == []


async def test_handle_body_keeps_the_flight_flag_while_the_charge_is_pending() -> None:
    billing = billing_for("cus_1")

    await charge_over(billing, PendingCharger()).handle_body(job_body())

    assert billing.abandoned == []
    assert billing.credited == []


async def test_handle_sqs_reports_the_failed_job_and_consumes_the_rest() -> None:
    gateway, customer_id = await gateway_with_customer()
    billing = FakeBilling(
        FakeRechargeAccount(
            account_id=ACCOUNT_ID, amount_micro=Micro(10_000_000), customer_id=customer_id
        ),
        fail_for=frozenset({"acc-broken"}),
    )
    event: SqsEvent = {
        "Records": [
            {"body": job_body("acc-broken", "job-broken"), "messageId": "sqs-0"},
            {"body": job_body(), "messageId": "sqs-1"},
        ]
    }

    response = await charge_over(billing, gateway).handle_sqs(event)

    assert response == {"batchItemFailures": [{"itemIdentifier": "sqs-0"}]}
    assert [row[0] for row in billing.credited] == [ACCOUNT_ID]

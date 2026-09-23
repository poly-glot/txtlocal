from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from txtlocal.entrypoints.billing_renewals import Billing, Renewals, RenewalsSummary
from txtlocal.shared.errors import NotFound, PaymentRequired
from txtlocal.shared.money import Micro

if TYPE_CHECKING:
    from txtlocal.slices.billing.service import DedicatedNumbers, DueNumber

ACCOUNT = "account-1"
SENDER = "sender-1"
NOW = datetime(2026, 9, 19, 6, 30, tzinfo=UTC)
RENEWS_AT = datetime(2026, 9, 19, 0, 0, tzinfo=UTC)
RENTAL_PRICE_MICRO = Micro(2_650_000)


@dataclass(frozen=True, slots=True)
class FakeDueNumber:
    account_id: str
    sender_id: str
    monthly_price_micro: Micro = RENTAL_PRICE_MICRO
    renewal_attempt: int = 0
    renews_at: datetime = RENEWS_AT
    value: str = "+447900000000"


def _fits_due_number(fake: FakeDueNumber) -> DueNumber:
    return fake


@dataclass(slots=True)
class FakeBilling:
    covered: frozenset[tuple[str, str]] = frozenset()
    missing: frozenset[str] = frozenset()
    charged: list[tuple[str, str, Micro]] = field(default_factory=list)
    periods: list[datetime] = field(default_factory=list)
    recharge_requested: list[str] = field(default_factory=list)

    async def charge_rental(
        self,
        account_id: str,
        sender_id: str,
        amount_micro: Micro,
        _now: datetime,
        period: datetime,
    ) -> None:
        if sender_id in self.missing:
            raise NotFound("Account not found")

        self.charged.append((account_id, sender_id, amount_micro))
        self.periods.append(period)
        if (account_id, sender_id) not in self.covered:
            raise PaymentRequired("insufficient balance")

    async def request_recharge(self, account_id: str, _now: datetime) -> None:
        self.recharge_requested.append(account_id)


def _fits_billing(fake: FakeBilling) -> Billing:
    return fake


@dataclass(slots=True)
class FakeDedicatedNumbers:
    due: list[FakeDueNumber] = field(default_factory=list)
    renewed: list[tuple[str, str]] = field(default_factory=list)
    retried: list[tuple[str, str]] = field(default_factory=list)
    released: list[tuple[str, str]] = field(default_factory=list)

    async def due_for_renewal(self, _now: datetime) -> list[FakeDueNumber]:
        return self.due

    async def rented_by(self, account_id: str) -> list[FakeDueNumber]:
        return [number for number in self.due if number.account_id == account_id]

    async def record_renewal(self, account_id: str, sender_id: str, _now: datetime) -> None:
        self.renewed.append((account_id, sender_id))

    async def record_renewal_attempt(self, account_id: str, sender_id: str, _now: datetime) -> None:
        self.retried.append((account_id, sender_id))

    async def release(self, account_id: str, sender_id: str) -> None:
        self.released.append((account_id, sender_id))


def _fits_numbers(fake: FakeDedicatedNumbers) -> DedicatedNumbers:
    return fake


def renewals_over(billing: FakeBilling, numbers: FakeDedicatedNumbers) -> Renewals:
    return Renewals(billing=billing, clock=lambda: NOW, numbers=numbers)


async def test_run_renews_a_covered_number_and_advances_it() -> None:
    billing = FakeBilling(covered=frozenset({(ACCOUNT, SENDER)}))
    numbers = FakeDedicatedNumbers(due=[FakeDueNumber(account_id=ACCOUNT, sender_id=SENDER)])

    summary = await renewals_over(billing, numbers).run()

    assert summary == RenewalsSummary(renewed=1)
    assert numbers.renewed == [(ACCOUNT, SENDER)]
    assert numbers.retried == []
    assert numbers.released == []
    assert billing.charged == [(ACCOUNT, SENDER, RENTAL_PRICE_MICRO)]


async def test_run_charges_the_numbers_own_monthly_price() -> None:
    billing = FakeBilling(covered=frozenset({(ACCOUNT, SENDER)}))
    numbers = FakeDedicatedNumbers(
        due=[FakeDueNumber(account_id=ACCOUNT, sender_id=SENDER, monthly_price_micro=Micro(9_999))]
    )

    await renewals_over(billing, numbers).run()

    assert billing.charged == [(ACCOUNT, SENDER, Micro(9_999))]


async def test_run_retries_an_uncovered_number_and_requests_a_recharge() -> None:
    billing = FakeBilling()
    numbers = FakeDedicatedNumbers(
        due=[FakeDueNumber(account_id=ACCOUNT, sender_id=SENDER, renewal_attempt=0)]
    )

    summary = await renewals_over(billing, numbers).run()

    assert summary == RenewalsSummary(retried=1)
    assert numbers.retried == [(ACCOUNT, SENDER)]
    assert numbers.released == []
    assert billing.recharge_requested == [ACCOUNT]


@pytest.mark.parametrize("attempt", range(7), ids=[f"day-{n + 1}-of-failure" for n in range(7)])
async def test_run_keeps_the_number_through_seven_days_of_failure(attempt: int) -> None:
    billing = FakeBilling()
    numbers = FakeDedicatedNumbers(
        due=[FakeDueNumber(account_id=ACCOUNT, sender_id=SENDER, renewal_attempt=attempt)]
    )

    summary = await renewals_over(billing, numbers).run()

    assert summary == RenewalsSummary(retried=1)
    assert numbers.released == []


async def test_run_releases_the_number_on_the_eighth_day_of_failure() -> None:
    billing = FakeBilling()
    numbers = FakeDedicatedNumbers(
        due=[FakeDueNumber(account_id=ACCOUNT, sender_id=SENDER, renewal_attempt=7)]
    )

    summary = await renewals_over(billing, numbers).run()

    assert summary == RenewalsSummary(released=1)
    assert numbers.released == [(ACCOUNT, SENDER)]
    assert numbers.retried == []
    assert billing.recharge_requested == [ACCOUNT]


async def test_run_sums_the_summary_across_many_due_numbers() -> None:
    billing = FakeBilling(covered=frozenset({(ACCOUNT, "renews-fine")}))
    numbers = FakeDedicatedNumbers(
        due=[
            FakeDueNumber(account_id=ACCOUNT, sender_id="renews-fine"),
            FakeDueNumber(account_id=ACCOUNT, sender_id="keeps-retrying", renewal_attempt=1),
            FakeDueNumber(account_id=ACCOUNT, sender_id="gets-released", renewal_attempt=7),
        ]
    )

    summary = await renewals_over(billing, numbers).run()

    assert summary == RenewalsSummary(released=1, renewed=1, retried=1)


async def test_run_charges_the_period_the_number_was_due_for() -> None:
    billing = FakeBilling(covered=frozenset({(ACCOUNT, SENDER)}))
    numbers = FakeDedicatedNumbers(due=[FakeDueNumber(account_id=ACCOUNT, sender_id=SENDER)])

    await renewals_over(billing, numbers).run()

    assert billing.periods == [RENEWS_AT]


async def test_run_counts_a_failing_number_and_keeps_going() -> None:
    billing = FakeBilling(
        covered=frozenset({(ACCOUNT, "renews-fine")}), missing=frozenset({"blows-up"})
    )
    numbers = FakeDedicatedNumbers(
        due=[
            FakeDueNumber(account_id=ACCOUNT, sender_id="blows-up"),
            FakeDueNumber(account_id=ACCOUNT, sender_id="renews-fine"),
        ]
    )

    summary = await renewals_over(billing, numbers).run()

    assert summary == RenewalsSummary(failed=1, renewed=1)
    assert numbers.renewed == [(ACCOUNT, "renews-fine")]


async def test_run_leaves_a_failing_number_untouched() -> None:
    billing = FakeBilling(missing=frozenset({SENDER}))
    numbers = FakeDedicatedNumbers(due=[FakeDueNumber(account_id=ACCOUNT, sender_id=SENDER)])

    await renewals_over(billing, numbers).run()

    assert numbers.renewed == []
    assert numbers.retried == []
    assert numbers.released == []

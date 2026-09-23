from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, assert_never

from txtlocal.entrypoints import wiring
from txtlocal.shared import runtime, telemetry
from txtlocal.shared.clock import utc_now
from txtlocal.shared.errors import AppError, PaymentRequired

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock
    from txtlocal.shared.money import Micro
    from txtlocal.slices.billing.service import DedicatedNumbers, DueNumber

RETRY_LIMIT = 7


class Billing(Protocol):
    async def charge_rental(
        self, account_id: str, sender_id: str, amount_micro: Micro, now: datetime, period: datetime
    ) -> None: ...

    async def request_recharge(self, account_id: str, now: datetime) -> None: ...


class RenewalOutcome(StrEnum):
    FAILED = "FAILED"
    RELEASED = "RELEASED"
    RENEWED = "RENEWED"
    RETRIED = "RETRIED"


@dataclass(frozen=True, slots=True)
class RenewalsSummary:
    failed: int = 0
    released: int = 0
    renewed: int = 0
    retried: int = 0

    def with_outcome(self, outcome: RenewalOutcome) -> RenewalsSummary:
        match outcome:
            case RenewalOutcome.FAILED:
                return replace(self, failed=self.failed + 1)
            case RenewalOutcome.RELEASED:
                return replace(self, released=self.released + 1)
            case RenewalOutcome.RENEWED:
                return replace(self, renewed=self.renewed + 1)
            case RenewalOutcome.RETRIED:
                return replace(self, retried=self.retried + 1)
            case _:
                assert_never(outcome)


@dataclass(frozen=True, slots=True)
class Renewals:
    billing: Billing
    clock: Clock
    numbers: DedicatedNumbers

    async def run(self) -> RenewalsSummary:
        now = self.clock()
        summary = RenewalsSummary()

        for due in await self.numbers.due_for_renewal(now):
            summary = summary.with_outcome(await self._renew(due, now))

        telemetry.log(
            "billing_renewals",
            failed=summary.failed,
            released=summary.released,
            renewed=summary.renewed,
            retried=summary.retried,
        )
        return summary

    async def _renew(self, due: DueNumber, now: datetime) -> RenewalOutcome:
        try:
            return await self._charge_one(due, now)
        except AppError as error:
            telemetry.log(
                "renewal_failed",
                account_id=due.account_id,
                error=error.code,
                level=telemetry.ERROR,
                sender_id=due.sender_id,
            )
            return RenewalOutcome.FAILED

    async def _charge_one(self, due: DueNumber, now: datetime) -> RenewalOutcome:
        try:
            await self.billing.charge_rental(
                due.account_id, due.sender_id, due.monthly_price_micro, now, due.renews_at
            )
        except PaymentRequired:
            return await self._on_uncovered(due, now)

        await self.numbers.record_renewal(due.account_id, due.sender_id, now)
        return RenewalOutcome.RENEWED

    async def _on_uncovered(self, due: DueNumber, now: datetime) -> RenewalOutcome:
        await self.billing.request_recharge(due.account_id, now)

        if due.renewal_attempt >= RETRY_LIMIT:
            await self.numbers.release(due.account_id, due.sender_id)
            return RenewalOutcome.RELEASED

        await self.numbers.record_renewal_attempt(due.account_id, due.sender_id, now)
        return RenewalOutcome.RETRIED


def renewals() -> Renewals:
    return Renewals(billing=wiring.billing(), clock=utc_now, numbers=wiring.dedicated_numbers())


def handler(_event: object, _context: object) -> None:
    runtime.run(renewals().run())


def main() -> None:
    runtime.run(renewals().run())


telemetry.configure()

if __name__ == "__main__":
    main()

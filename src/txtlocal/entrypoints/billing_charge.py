from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, assert_never

from txtlocal.shared import runtime, telemetry
from txtlocal.shared.bus import BatchResponse, SqsEvent, partial_batch
from txtlocal.shared.clock import utc_now
from txtlocal.slices.billing.gateway import ChargeOutcome, ChargeStatus, OffSessionCharge
from txtlocal.slices.billing.model import RechargeJob

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock
    from txtlocal.shared.money import Micro


class RechargeAccount(Protocol):
    @property
    def account_id(self) -> str: ...

    @property
    def amount_micro(self) -> Micro: ...

    @property
    def customer_id(self) -> str: ...


class Billing(Protocol):
    async def abandon_recharge(self, account_id: str) -> None: ...

    async def credit_recharge(
        self, account_id: str, amount_micro: Micro, provider_ref: str, now: datetime
    ) -> None: ...

    async def decline_recharge(
        self, idempotency_key: str, account_id: str, decline_code: str, now: datetime
    ) -> None: ...

    async def recharge_account(self, account_id: str) -> RechargeAccount | None: ...


class Charger(Protocol):
    async def charge_off_session(self, charge: OffSessionCharge) -> ChargeOutcome: ...


def idempotency_key_of(job: RechargeJob) -> str:
    return f"recharge_{job.job_id}"


@dataclass(frozen=True, slots=True)
class BillingCharge:
    billing: Billing
    clock: Clock
    gateway: Charger

    async def handle_body(self, body: str) -> None:
        job = RechargeJob.model_validate_json(body)
        now = self.clock()

        account = await self.billing.recharge_account(job.account_id)
        if account is None:
            await self.billing.abandon_recharge(job.account_id)
            telemetry.log("recharge", account_id=job.account_id, outcome="not_eligible")
            return

        idempotency_key = idempotency_key_of(job)
        outcome = await self.gateway.charge_off_session(
            OffSessionCharge(
                account_id=job.account_id,
                amount_micro=account.amount_micro,
                customer_id=account.customer_id,
                idempotency_key=idempotency_key,
            )
        )

        await self._settle(job.account_id, idempotency_key, account.amount_micro, outcome, now)

    async def handle_sqs(self, event: SqsEvent) -> BatchResponse:
        return await partial_batch(event, self.handle_body, "recharge_failed")

    async def _settle(
        self,
        account_id: str,
        idempotency_key: str,
        amount_micro: Micro,
        outcome: ChargeOutcome,
        now: datetime,
    ) -> None:
        match outcome.status:
            case ChargeStatus.SUCCEEDED:
                provider_ref = outcome.provider_ref or idempotency_key
                await self.billing.credit_recharge(account_id, amount_micro, provider_ref, now)
                telemetry.log("recharge", account_id=account_id, outcome="succeeded")
            case ChargeStatus.DECLINED:
                await self.billing.decline_recharge(
                    idempotency_key, account_id, outcome.decline_code or "declined", now
                )
                telemetry.log("recharge", account_id=account_id, outcome="declined")
            case ChargeStatus.ERRORED:
                await self.billing.abandon_recharge(account_id)
                telemetry.log("recharge", account_id=account_id, outcome="errored")
            case ChargeStatus.PENDING:
                telemetry.log("recharge", account_id=account_id, outcome="pending")
            case _:
                assert_never(outcome.status)


from txtlocal.entrypoints import wiring


def billing_charge() -> BillingCharge:
    return BillingCharge(billing=wiring.billing(), clock=utc_now, gateway=wiring.payment_gateway())


def handler(event: SqsEvent, _context: object) -> BatchResponse:
    return runtime.run(billing_charge().handle_sqs(event))


telemetry.configure()

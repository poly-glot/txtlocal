import base64
import json
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, TypedDict

from fastapi import APIRouter, Request, Response

from txtlocal.shared import runtime, telemetry
from txtlocal.shared.clock import utc_now
from txtlocal.shared.errors import AppError, Internal
from txtlocal.slices.billing.gateway import RECHARGE_KIND, SETUP_MODE

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock
    from txtlocal.shared.money import Micro
    from txtlocal.slices.billing.gateway import PaymentEvent, PaymentGateway

CHECKOUT_COMPLETED = "checkout.session.completed"
LOCAL_PATH = "/api/stripe-webhook"
PAYMENT_INTENT_SUCCEEDED = "payment_intent.succeeded"
SETUP_SUCCEEDED = "setup_intent.succeeded"
SIGNATURE_HEADER = "stripe-signature"


class WebhookOutcome(StrEnum):
    CREDITED = "CREDITED"
    IGNORED = "IGNORED"
    RECORDED = "RECORDED"


@dataclass(frozen=True, slots=True)
class WebhookAnswer:
    outcome: WebhookOutcome


class Billing(Protocol):
    async def credit_recharge(
        self, account_id: str, amount_micro: Micro, provider_ref: str, now: datetime
    ) -> None: ...

    async def credit_top_up(self, event: PaymentEvent, now: datetime) -> None: ...


class FunctionUrlEvent(TypedDict):
    body: str
    headers: dict[str, str]
    isBase64Encoded: bool


class FunctionUrlResponse(TypedDict):
    body: str
    statusCode: int


@dataclass(frozen=True, slots=True)
class StripeWebhook:
    billing: Billing
    clock: Clock
    gateway: PaymentGateway

    async def handle(self, payload: bytes, signature: str) -> WebhookAnswer:
        event = self.gateway.verify_webhook(payload, signature, self.clock())

        if event.event_type == CHECKOUT_COMPLETED and event.mode != SETUP_MODE:
            await self.billing.credit_top_up(await self._with_invoice(event), self.clock())
            return WebhookAnswer(outcome=WebhookOutcome.CREDITED)

        if event.event_type == PAYMENT_INTENT_SUCCEEDED and event.kind == RECHARGE_KIND:
            return await self._credit_recharge(event)

        if event.event_type == SETUP_SUCCEEDED:
            return await self._record_card(event)

        return WebhookAnswer(outcome=WebhookOutcome.IGNORED)

    async def _credit_recharge(self, event: PaymentEvent) -> WebhookAnswer:
        if event.account_id is None or event.amount_micro is None or event.provider_ref is None:
            return WebhookAnswer(outcome=WebhookOutcome.IGNORED)

        await self.billing.credit_recharge(
            event.account_id, event.amount_micro, event.provider_ref, self.clock()
        )
        return WebhookAnswer(outcome=WebhookOutcome.CREDITED)

    async def _record_card(self, event: PaymentEvent) -> WebhookAnswer:
        if event.customer_id is not None and event.payment_method_id is not None:
            await self.gateway.set_default(event.customer_id, event.payment_method_id)
        return WebhookAnswer(outcome=WebhookOutcome.RECORDED)

    async def _with_invoice(self, event: PaymentEvent) -> PaymentEvent:
        if event.invoice_id is None:
            return event

        invoice = await self.gateway.invoice(event.invoice_id)
        return replace(event, invoice_number=invoice.number, invoice_url=invoice.url)


def body_of(event: FunctionUrlEvent) -> bytes:
    body = event.get("body", "")
    if event.get("isBase64Encoded"):
        return base64.b64decode(body)
    return body.encode()


def header_of(event: FunctionUrlEvent, name: str) -> str:
    return event.get("headers", {}).get(name, "")


def response_of(status_code: int, body: object) -> FunctionUrlResponse:
    return {"body": json.dumps(body), "statusCode": status_code}


def build_local_router(webhook: StripeWebhook) -> APIRouter:
    router = APIRouter()

    @router.post(LOCAL_PATH, include_in_schema=False)
    async def receive(request: Request) -> Response:
        event = FunctionUrlEvent(
            body=(await request.body()).decode(),
            headers=dict(request.headers),
            isBase64Encoded=False,
        )
        answer = await handle_event(webhook, event)
        return Response(
            answer["body"], media_type="application/json", status_code=answer["statusCode"]
        )

    return router


from txtlocal.entrypoints import wiring


def stripe_webhook() -> StripeWebhook:
    return StripeWebhook(billing=wiring.billing(), clock=utc_now, gateway=wiring.payment_gateway())


async def handle_event(webhook: StripeWebhook, event: FunctionUrlEvent) -> FunctionUrlResponse:
    try:
        answer = await webhook.handle(body_of(event), header_of(event, SIGNATURE_HEADER))
    except AppError as error:
        level = telemetry.ERROR if error.status >= Internal.status else telemetry.WARNING
        telemetry.log("stripe_webhook_refused", code=error.code, level=level, status=error.status)
        return response_of(error.status, {"code": error.code, "message": error.public_message()})

    telemetry.log("stripe_webhook", outcome=answer.outcome)
    return response_of(200, {"outcome": answer.outcome})


def handler(event: FunctionUrlEvent, _context: object) -> FunctionUrlResponse:
    return runtime.run(handle_event(stripe_webhook(), event))


telemetry.configure()

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from txtlocal.entrypoints.stripe_webhook import (
    LOCAL_PATH,
    SIGNATURE_HEADER,
    Billing,
    StripeWebhook,
    WebhookAnswer,
    WebhookOutcome,
    build_local_router,
)
from txtlocal.shared.errors import BadRequest
from txtlocal.shared.money import Micro
from txtlocal.slices.billing.gateway import (
    INVALID_SIGNATURE,
    RECHARGE_KIND,
    SETUP_MODE,
    PaymentEvent,
)
from txtlocal.slices.billing.tests.fakes import INVOICE_URL, FakePaymentGateway

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
ACCOUNT_ID = "acc-1"


@dataclass(slots=True)
class FakeBilling:
    credited: list[PaymentEvent] = field(default_factory=list)
    recharged: list[tuple[str, Micro, str]] = field(default_factory=list)

    async def credit_recharge(
        self, account_id: str, amount_micro: Micro, provider_ref: str, _now: datetime
    ) -> None:
        self.recharged.append((account_id, amount_micro, provider_ref))

    async def credit_top_up(self, event: PaymentEvent, _now: datetime) -> None:
        self.credited.append(event)


def _fits(fake: FakeBilling) -> Billing:
    return fake


def gateway_over() -> FakePaymentGateway:
    return FakePaymentGateway()


def webhook_over(billing: FakeBilling, gateway: FakePaymentGateway) -> StripeWebhook:
    return StripeWebhook(billing=billing, clock=lambda: NOW, gateway=gateway)


def fake_signature() -> str:
    return f"t={int(NOW.timestamp())},v1=fake"


def checkout_completed_payload(
    account_id: str, top_up_id: str, invoice_id: str | None = "in_1"
) -> bytes:
    return json.dumps(
        {
            "id": "evt_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_1",
                    "invoice": invoice_id,
                    "metadata": {"accountId": account_id, "topUpId": top_up_id},
                }
            },
        }
    ).encode()


def setup_checkout_payload() -> bytes:
    return json.dumps(
        {
            "id": "evt_setup_checkout",
            "type": "checkout.session.completed",
            "data": {"object": {"customer": "cus_1", "id": "cs_1", "mode": SETUP_MODE}},
        }
    ).encode()


def payment_intent_payload(metadata: dict[str, str], amount: int = 1_000) -> bytes:
    return json.dumps(
        {
            "id": "evt_pi",
            "type": "payment_intent.succeeded",
            "data": {
                "object": {
                    "amount": amount,
                    "customer": "cus_1",
                    "id": "pi_1",
                    "metadata": metadata,
                }
            },
        }
    ).encode()


async def test_handle_credits_a_completed_checkout() -> None:
    billing = FakeBilling()
    webhook = webhook_over(billing, gateway_over())

    answer = await webhook.handle(checkout_completed_payload("acc-1", "top-1"), fake_signature())

    assert answer == WebhookAnswer(outcome=WebhookOutcome.CREDITED)
    assert len(billing.credited) == 1
    assert (billing.credited[0].account_id, billing.credited[0].top_up_id) == ("acc-1", "top-1")
    assert billing.credited[0].invoice_number == "INV-1"


async def test_handle_links_the_invoice_stripe_created_for_the_checkout() -> None:
    billing = FakeBilling()
    webhook = webhook_over(billing, gateway_over())

    await webhook.handle(checkout_completed_payload("acc-1", "top-1"), fake_signature())

    assert billing.credited[0].invoice_url == f"{INVOICE_URL}in_1"


async def test_handle_credits_a_checkout_that_created_no_invoice() -> None:
    billing = FakeBilling()
    webhook = webhook_over(billing, gateway_over())

    await webhook.handle(checkout_completed_payload("acc-1", "top-1", None), fake_signature())

    assert [(event.top_up_id, event.invoice_number) for event in billing.credited] == [
        ("top-1", None)
    ]


async def test_handle_sets_the_new_card_default_on_setup_succeeded() -> None:
    gateway = gateway_over()
    customer_id = await gateway.ensure_customer("acc-1", "a@b.example")
    new_pm = gateway.attach_demo_card(customer_id)
    webhook = webhook_over(FakeBilling(), gateway)
    payload = json.dumps(
        {
            "id": "evt_2",
            "type": "setup_intent.succeeded",
            "data": {"object": {"customer": customer_id, "payment_method": new_pm}},
        }
    ).encode()

    answer = await webhook.handle(payload, fake_signature())

    assert answer == WebhookAnswer(outcome=WebhookOutcome.RECORDED)
    cards = await gateway.payment_methods(customer_id)
    assert next(card for card in cards if card.payment_method_id == new_pm).is_default


async def test_handle_ignores_an_unhandled_event_type() -> None:
    webhook = webhook_over(FakeBilling(), gateway_over())
    payload = json.dumps({"id": "evt_3", "type": "invoice.paid", "data": {"object": {}}}).encode()

    answer = await webhook.handle(payload, fake_signature())

    assert answer == WebhookAnswer(outcome=WebhookOutcome.IGNORED)


async def test_handle_rejects_a_signature_that_is_not_the_fake_shape() -> None:
    webhook = webhook_over(FakeBilling(), gateway_over())

    with pytest.raises(BadRequest):
        await webhook.handle(b"{}", f"t={int(NOW.timestamp())},v1=not-fake")


async def test_handle_ignores_a_setup_mode_checkout_session() -> None:
    billing = FakeBilling()
    webhook = webhook_over(billing, gateway_over())

    answer = await webhook.handle(setup_checkout_payload(), fake_signature())

    assert answer == WebhookAnswer(outcome=WebhookOutcome.IGNORED)
    assert billing.credited == []


async def test_handle_credits_a_recharge_payment_intent_that_settled_later() -> None:
    billing = FakeBilling()
    webhook = webhook_over(billing, gateway_over())
    payload = payment_intent_payload({"accountId": ACCOUNT_ID, "kind": RECHARGE_KIND})

    answer = await webhook.handle(payload, fake_signature())

    assert answer == WebhookAnswer(outcome=WebhookOutcome.CREDITED)
    assert billing.recharged == [(ACCOUNT_ID, Micro(10_000_000), "pi_1")]


async def test_handle_ignores_a_payment_intent_that_is_not_a_recharge() -> None:
    billing = FakeBilling()
    webhook = webhook_over(billing, gateway_over())

    answer = await webhook.handle(payment_intent_payload({}), fake_signature())

    assert answer == WebhookAnswer(outcome=WebhookOutcome.IGNORED)
    assert billing.recharged == []


async def test_handle_ignores_a_recharge_payment_intent_without_an_account() -> None:
    billing = FakeBilling()
    webhook = webhook_over(billing, gateway_over())

    answer = await webhook.handle(payment_intent_payload({"kind": RECHARGE_KIND}), fake_signature())

    assert answer == WebhookAnswer(outcome=WebhookOutcome.IGNORED)
    assert billing.recharged == []


def test_local_route_hands_a_signed_event_to_the_webhook() -> None:
    billing = FakeBilling()
    app = FastAPI()
    app.include_router(build_local_router(webhook_over(billing, gateway_over())))

    response = TestClient(app).post(
        LOCAL_PATH,
        content=checkout_completed_payload(ACCOUNT_ID, "top-1"),
        headers={SIGNATURE_HEADER: fake_signature()},
    )

    assert response.status_code == HTTPStatus.OK
    assert [event.top_up_id for event in billing.credited] == ["top-1"]


def test_local_route_answers_a_bad_signature_with_the_refusal() -> None:
    app = FastAPI()
    app.include_router(build_local_router(webhook_over(FakeBilling(), gateway_over())))

    response = TestClient(app).post(
        LOCAL_PATH, content=b"{}", headers={SIGNATURE_HEADER: "t=1,v1=forged"}
    )

    assert (response.status_code, response.json()["message"]) == (
        HTTPStatus.BAD_REQUEST,
        INVALID_SIGNATURE,
    )

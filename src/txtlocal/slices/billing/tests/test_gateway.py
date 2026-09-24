import hmac
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
from urllib.parse import parse_qs

import httpx
import pytest

from txtlocal.shared.errors import BadRequest
from txtlocal.shared.money import Micro
from txtlocal.slices.billing.gateway import (
    RECHARGE_KIND,
    SETUP_MODE,
    ChargeStatus,
    Invoice,
    OffSessionCharge,
    ReturnUrls,
    StripeGateway,
)

ACCOUNT_ID = "acc-1"
CUSTOMER_ID = "cus_1"
DEFAULT_CARD = "pm_1"
INVOICE_ID = "in_1"
INVOICE_URL = "https://invoice.stripe.com/i/in_1"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
PAYLOAD = b'{"id": "evt_1", "type": "checkout.session.completed"}'
WEBHOOK_SECRET = "whsec_test"


@dataclass(slots=True)
class StripeServer:
    payment_intent_status: str = "succeeded"
    posts: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    def handle(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == f"/v1/invoices/{INVOICE_ID}":
            return httpx.Response(200, json={"hosted_invoice_url": INVOICE_URL, "number": "INV-1"})

        if request.method == "GET":
            return httpx.Response(
                200, json={"invoice_settings": {"default_payment_method": DEFAULT_CARD}}
            )

        self.posts[request.url.path] = parse_qs(request.content.decode())
        return httpx.Response(200, json={"id": "pi_1", "status": self.payment_intent_status})


def gateway_over(server: StripeServer, webhook_secret: str = WEBHOOK_SECRET) -> StripeGateway:
    return StripeGateway(
        http=httpx.AsyncClient(transport=httpx.MockTransport(server.handle)),
        secret_key="sk_test",
        webhook_secret=webhook_secret,
    )


def signed(payload: bytes, secret: str) -> str:
    timestamp = int(NOW.timestamp())
    digest = hmac.new(secret.encode(), f"{timestamp}.".encode() + payload, sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


async def charge(server: StripeServer) -> None:
    await gateway_over(server).charge_off_session(
        OffSessionCharge(
            account_id=ACCOUNT_ID,
            amount_micro=Micro(10_000_000),
            customer_id=CUSTOMER_ID,
            idempotency_key="recharge_job-1",
        )
    )


async def test_charge_off_session_marks_the_intent_as_a_recharge() -> None:
    server = StripeServer()

    await charge(server)

    assert server.posts["/v1/payment_intents"]["metadata[kind]"] == [RECHARGE_KIND]


async def test_charge_off_session_names_the_account_on_the_intent() -> None:
    server = StripeServer()

    await charge(server)

    assert server.posts["/v1/payment_intents"]["metadata[accountId]"] == [ACCOUNT_ID]


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("succeeded", ChargeStatus.SUCCEEDED),
        ("processing", ChargeStatus.PENDING),
        ("requires_action", ChargeStatus.PENDING),
    ],
    ids=["settled-now", "settling-later", "waiting-on-the-customer"],
)
async def test_charge_off_session_reads_the_intent_status(
    status: str, expected: ChargeStatus
) -> None:
    server = StripeServer(payment_intent_status=status)

    outcome = await gateway_over(server).charge_off_session(
        OffSessionCharge(
            account_id=ACCOUNT_ID,
            amount_micro=Micro(10_000_000),
            customer_id=CUSTOMER_ID,
            idempotency_key="recharge_job-1",
        )
    )

    assert outcome.status is expected


async def test_setup_session_asks_stripe_for_a_setup_mode_checkout() -> None:
    server = StripeServer()

    await gateway_over(server).setup_session(
        CUSTOMER_ID, ReturnUrls(cancel_url="http://x/billing", success_url="http://x/billing")
    )

    assert server.posts["/v1/checkout/sessions"]["mode"] == [SETUP_MODE]


async def test_invoice_reads_the_number_and_hosted_url() -> None:
    invoice = await gateway_over(StripeServer()).invoice(INVOICE_ID)

    assert invoice == Invoice(number="INV-1", url=INVOICE_URL)


def test_verify_webhook_accepts_a_payload_signed_with_the_secret() -> None:
    event = gateway_over(StripeServer()).verify_webhook(
        PAYLOAD, signed(PAYLOAD, WEBHOOK_SECRET), NOW
    )

    assert event.event_id == "evt_1"


def test_verify_webhook_refuses_every_signature_without_a_secret() -> None:
    gateway = gateway_over(StripeServer(), webhook_secret="")

    with pytest.raises(BadRequest):
        gateway.verify_webhook(PAYLOAD, signed(PAYLOAD, ""), NOW)

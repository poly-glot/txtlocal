import hmac
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from http import HTTPStatus
from typing import TYPE_CHECKING, Protocol, cast

import httpx
from fastapi import APIRouter, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from txtlocal.shared.errors import BadRequest, NotFound, Upstream
from txtlocal.shared.money import MICRO_PER_PENCE, Micro, format_price, micro_to_pence

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock

CONNECT_TIMEOUT_SECONDS = 5.0
TOTAL_TIMEOUT_SECONDS = 30.0
SIGNATURE_TOLERANCE_SECONDS = 300
STRIPE_API = "https://api.stripe.com/v1"

CARD_NOT_FOUND = "No saved card with that id"
DEMO_NOT_FOUND = "This demo checkout session has expired"
INVALID_SIGNATURE = "Invalid webhook signature"
NO_DEFAULT_CARD = "no_default_card"
PAYMENT_MODE = "payment"
RECHARGE_KIND = "recharge"
SETUP_MODE = "setup"


class ChargeStatus(StrEnum):
    DECLINED = "DECLINED"
    ERRORED = "ERRORED"
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"


@dataclass(frozen=True, slots=True)
class Card:
    brand: str
    cardholder_name: str
    exp_month: int
    exp_year: int
    last4: str
    payment_method_id: str
    is_default: bool = False


@dataclass(frozen=True, slots=True)
class Pack:
    account_id: str
    amount_micro: Micro
    code: str
    name: str
    top_up_id: str


@dataclass(frozen=True, slots=True)
class ReturnUrls:
    cancel_url: str
    success_url: str


@dataclass(frozen=True, slots=True)
class CheckoutSession:
    session_id: str
    url: str


@dataclass(frozen=True, slots=True)
class OffSessionCharge:
    account_id: str
    amount_micro: Micro
    customer_id: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class ChargeOutcome:
    status: ChargeStatus
    decline_code: str | None = None
    invoice_number: str | None = None
    invoice_url: str | None = None
    provider_ref: str | None = None


@dataclass(frozen=True, slots=True)
class PaymentEvent:
    event_id: str
    event_type: str
    account_id: str | None = None
    amount_micro: Micro | None = None
    customer_id: str | None = None
    invoice_number: str | None = None
    invoice_url: str | None = None
    kind: str | None = None
    mode: str | None = None
    payment_method_id: str | None = None
    provider_ref: str | None = None
    top_up_id: str | None = None


class PaymentGateway(Protocol):
    async def ensure_customer(self, account_id: str, email: str) -> str: ...

    async def checkout(
        self, customer_id: str, pack: Pack, urls: ReturnUrls, idempotency_key: str
    ) -> CheckoutSession: ...

    async def setup_session(self, customer_id: str, urls: ReturnUrls) -> CheckoutSession: ...

    async def payment_methods(self, customer_id: str) -> list[Card]: ...

    async def set_default(self, customer_id: str, payment_method_id: str) -> None: ...

    async def detach(self, payment_method_id: str) -> None: ...

    async def charge_off_session(self, charge: OffSessionCharge) -> ChargeOutcome: ...

    def verify_webhook(self, payload: bytes, signature: str, now: datetime) -> PaymentEvent: ...


class Webhook(Protocol):
    async def handle(self, payload: bytes, signature: str) -> object: ...


def as_mapping(value: object) -> Mapping[str, object]:
    return cast("dict[str, object]", value) if isinstance(value, dict) else {}


def string_field(fields: Mapping[str, object], name: str) -> str | None:
    value = fields.get(name)
    return value if isinstance(value, str) else None


def int_field(fields: Mapping[str, object], name: str) -> int:
    value = fields.get(name)
    return value if isinstance(value, int) else 0


def amount_micro_of(fields: Mapping[str, object]) -> Micro | None:
    amount = fields.get("amount")
    return Micro(amount * MICRO_PER_PENCE) if isinstance(amount, int) else None


def payment_event_of(body: Mapping[str, object]) -> PaymentEvent:
    fields = as_mapping(as_mapping(body.get("data")).get("object"))
    metadata = as_mapping(fields.get("metadata"))
    invoice = as_mapping(fields.get("invoice"))

    return PaymentEvent(
        event_id=string_field(body, "id") or "",
        event_type=string_field(body, "type") or "",
        account_id=string_field(metadata, "accountId"),
        amount_micro=amount_micro_of(fields),
        customer_id=string_field(fields, "customer"),
        invoice_number=string_field(invoice, "number"),
        invoice_url=string_field(invoice, "hosted_invoice_url"),
        kind=string_field(metadata, "kind"),
        mode=string_field(fields, "mode"),
        payment_method_id=string_field(fields, "payment_method"),
        provider_ref=string_field(fields, "id"),
        top_up_id=string_field(metadata, "topUpId"),
    )


def signature_fields(header: str) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    for part in header.split(","):
        name, _, value = part.strip().partition("=")
        if value:
            fields.append((name, value))
    return fields


@dataclass(frozen=True, slots=True)
class StripeGateway:
    http: httpx.AsyncClient
    secret_key: str
    webhook_secret: str

    async def ensure_customer(self, account_id: str, email: str) -> str:
        response = await self._post(
            "/customers",
            {"email": email, "metadata[accountId]": account_id},
            idempotency_key=f"customer_{account_id}",
        )
        return string_field(response, "id") or ""

    async def checkout(
        self, customer_id: str, pack: Pack, urls: ReturnUrls, idempotency_key: str
    ) -> CheckoutSession:
        response = await self._post(
            "/checkout/sessions",
            {
                "cancel_url": urls.cancel_url,
                "customer": customer_id,
                "invoice_creation[enabled]": "true",
                "line_items[0][price_data][currency]": "gbp",
                "line_items[0][price_data][product_data][name]": pack.name,
                "line_items[0][price_data][unit_amount]": str(micro_to_pence(pack.amount_micro)),
                "line_items[0][quantity]": "1",
                "metadata[accountId]": pack.account_id,
                "metadata[topUpId]": pack.top_up_id,
                "mode": PAYMENT_MODE,
                "success_url": urls.success_url,
            },
            idempotency_key=idempotency_key,
        )
        return session_of(response)

    async def setup_session(self, customer_id: str, urls: ReturnUrls) -> CheckoutSession:
        response = await self._post(
            "/checkout/sessions",
            {
                "cancel_url": urls.cancel_url,
                "customer": customer_id,
                "mode": SETUP_MODE,
                "success_url": urls.success_url,
            },
        )
        return session_of(response)

    async def payment_methods(self, customer_id: str) -> list[Card]:
        default_id = await self._default_payment_method(customer_id)
        listing = await self._get(f"/payment_methods?customer={customer_id}&type=card")
        data = listing.get("data")
        items = data if isinstance(data, list) else []
        return [card_of(as_mapping(item), default_id) for item in items]

    async def set_default(self, customer_id: str, payment_method_id: str) -> None:
        await self._post(
            f"/customers/{customer_id}",
            {"invoice_settings[default_payment_method]": payment_method_id},
        )

    async def detach(self, payment_method_id: str) -> None:
        await self._post(f"/payment_methods/{payment_method_id}/detach", {})

    async def charge_off_session(self, charge: OffSessionCharge) -> ChargeOutcome:
        default_pm = await self._default_payment_method(charge.customer_id)
        if default_pm is None:
            return ChargeOutcome(status=ChargeStatus.DECLINED, decline_code=NO_DEFAULT_CARD)

        response = await self._request(
            "POST",
            "/payment_intents",
            {
                "amount": str(micro_to_pence(charge.amount_micro)),
                "confirm": "true",
                "currency": "gbp",
                "customer": charge.customer_id,
                "metadata[accountId]": charge.account_id,
                "metadata[kind]": RECHARGE_KIND,
                "off_session": "true",
                "payment_method": default_pm,
            },
            charge.idempotency_key,
        )
        body = as_mapping(response.json()) if response.content else {}
        if response.is_success:
            return charge_outcome_of(body)
        return declined_outcome_of(body, response.status_code)

    def verify_webhook(self, payload: bytes, signature: str, now: datetime) -> PaymentEvent:
        if not self._signature_valid(payload, signature, now):
            raise BadRequest(INVALID_SIGNATURE)
        return payment_event_of(as_mapping(json.loads(payload)))

    def _signature_valid(self, payload: bytes, signature: str, now: datetime) -> bool:
        fields = signature_fields(signature)
        timestamps = [value for name, value in fields if name == "t"]
        if len(timestamps) != 1 or not timestamps[0].lstrip("-").isdigit():
            return False
        if abs(now.timestamp() - int(timestamps[0])) > SIGNATURE_TOLERANCE_SECONDS:
            return False

        expected = hmac.new(
            self.webhook_secret.encode(), f"{timestamps[0]}.".encode() + payload, sha256
        ).hexdigest()
        return any(hmac.compare_digest(expected, value) for name, value in fields if name == "v1")

    async def _default_payment_method(self, customer_id: str) -> str | None:
        customer = await self._get(f"/customers/{customer_id}")
        return string_field(as_mapping(customer.get("invoice_settings")), "default_payment_method")

    async def _request(
        self, method: str, path: str, data: Mapping[str, str] | None, idempotency_key: str | None
    ) -> httpx.Response:
        headers = {"Authorization": f"Bearer {self.secret_key}"}
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        try:
            return await self.http.request(
                method,
                f"{STRIPE_API}{path}",
                data=data,
                headers=headers,
                timeout=httpx.Timeout(TOTAL_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS),
            )
        except httpx.HTTPError as error:
            raise Upstream(f"stripe {method} {path} failed: {error}") from error

    async def _post(
        self, path: str, data: Mapping[str, str], *, idempotency_key: str | None = None
    ) -> Mapping[str, object]:
        response = await self._request("POST", path, data, idempotency_key)
        if not response.is_success:
            raise stripe_upstream_error(response)
        return as_mapping(response.json())

    async def _get(self, path: str) -> Mapping[str, object]:
        response = await self._request("GET", path, None, None)
        if not response.is_success:
            raise stripe_upstream_error(response)
        return as_mapping(response.json())


def session_of(response: Mapping[str, object]) -> CheckoutSession:
    return CheckoutSession(
        session_id=string_field(response, "id") or "", url=string_field(response, "url") or ""
    )


def card_of(payment_method: Mapping[str, object], default_id: str | None) -> Card:
    pm_id = string_field(payment_method, "id") or ""
    details = as_mapping(payment_method.get("card"))
    name = string_field(as_mapping(payment_method.get("billing_details")), "name")
    return Card(
        brand=string_field(details, "brand") or "",
        cardholder_name=name or "",
        exp_month=int_field(details, "exp_month"),
        exp_year=int_field(details, "exp_year"),
        is_default=pm_id == default_id,
        last4=string_field(details, "last4") or "",
        payment_method_id=pm_id,
    )


def stripe_error_details(response: httpx.Response) -> Mapping[str, object]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return as_mapping(as_mapping(body).get("error"))


def stripe_upstream_error(response: httpx.Response) -> Upstream:
    details = stripe_error_details(response)
    code = (
        string_field(details, "code") or string_field(details, "type") or str(response.status_code)
    )
    return Upstream(f"stripe: {code}")


def charge_outcome_of(payment_intent: Mapping[str, object]) -> ChargeOutcome:
    provider_ref = string_field(payment_intent, "id")
    if string_field(payment_intent, "status") == "succeeded":
        return ChargeOutcome(status=ChargeStatus.SUCCEEDED, provider_ref=provider_ref)
    return ChargeOutcome(status=ChargeStatus.PENDING, provider_ref=provider_ref)


def declined_outcome_of(body: Mapping[str, object], status_code: int) -> ChargeOutcome:
    details = as_mapping(body.get("error"))
    if string_field(details, "type") == "card_error":
        code = (
            string_field(details, "decline_code")
            or string_field(details, "code")
            or "card_declined"
        )
        return ChargeOutcome(status=ChargeStatus.DECLINED, decline_code=code)
    return ChargeOutcome(
        status=ChargeStatus.ERRORED, decline_code=string_field(details, "code") or str(status_code)
    )


SEED_VISA = Card(
    brand="visa",
    cardholder_name="Demo Card",
    exp_month=12,
    exp_year=2035,
    last4="4242",
    payment_method_id="pm_demo_4242",
    is_default=True,
)
SEED_DECLINING = Card(
    brand="visa",
    cardholder_name="Demo Card",
    exp_month=12,
    exp_year=2035,
    last4="0002",
    payment_method_id="pm_demo_0002",
)


@dataclass(slots=True)
class StoredCustomer:
    cards: dict[str, Card] = field(default_factory=dict)
    default: str | None = None


@dataclass(frozen=True, slots=True)
class StoredSession:
    customer_id: str
    mode: str
    success_url: str
    account_id: str | None = None
    amount_micro: Micro | None = None
    top_up_id: str | None = None


@dataclass(slots=True)
class FakeStore:
    customers: dict[str, StoredCustomer] = field(default_factory=dict)
    sessions: dict[str, StoredSession] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FakePaymentGateway:
    clock: Clock
    public_base_url: str
    store: FakeStore = field(default_factory=FakeStore)

    async def ensure_customer(self, _account_id: str, _email: str) -> str:
        customer_id = f"cus_demo_{uuid.uuid7()}"
        self.store.customers[customer_id] = StoredCustomer(
            cards={
                SEED_VISA.payment_method_id: SEED_VISA,
                SEED_DECLINING.payment_method_id: SEED_DECLINING,
            },
            default=SEED_VISA.payment_method_id,
        )
        return customer_id

    async def checkout(
        self, customer_id: str, pack: Pack, urls: ReturnUrls, _idempotency_key: str
    ) -> CheckoutSession:
        session_id = f"cs_demo_{uuid.uuid7()}"
        self.store.sessions[session_id] = StoredSession(
            account_id=pack.account_id,
            amount_micro=pack.amount_micro,
            customer_id=customer_id,
            mode=PAYMENT_MODE,
            success_url=urls.success_url,
            top_up_id=pack.top_up_id,
        )
        return CheckoutSession(session_id=session_id, url=self._url(session_id))

    async def setup_session(self, customer_id: str, urls: ReturnUrls) -> CheckoutSession:
        session_id = f"cs_demo_{uuid.uuid7()}"
        self.store.sessions[session_id] = StoredSession(
            customer_id=customer_id, mode=SETUP_MODE, success_url=urls.success_url
        )
        return CheckoutSession(session_id=session_id, url=self._url(session_id))

    async def payment_methods(self, customer_id: str) -> list[Card]:
        stored = self.store.customers.get(customer_id)
        if stored is None:
            return []
        return [
            replace(card, is_default=pm_id == stored.default)
            for pm_id, card in stored.cards.items()
        ]

    async def set_default(self, customer_id: str, payment_method_id: str) -> None:
        stored = self.store.customers.get(customer_id)
        if stored is None or payment_method_id not in stored.cards:
            raise NotFound(CARD_NOT_FOUND)
        stored.default = payment_method_id

    async def detach(self, payment_method_id: str) -> None:
        for stored in self.store.customers.values():
            if payment_method_id in stored.cards:
                del stored.cards[payment_method_id]
                if stored.default == payment_method_id:
                    stored.default = None
                return
        raise NotFound(CARD_NOT_FOUND)

    async def charge_off_session(self, charge: OffSessionCharge) -> ChargeOutcome:
        stored = self.store.customers.get(charge.customer_id)
        default_id = stored.default if stored is not None else None
        if default_id is None:
            return ChargeOutcome(status=ChargeStatus.DECLINED, decline_code=NO_DEFAULT_CARD)
        if default_id == SEED_DECLINING.payment_method_id:
            return ChargeOutcome(status=ChargeStatus.DECLINED, decline_code="card_declined")
        return ChargeOutcome(
            status=ChargeStatus.SUCCEEDED, provider_ref=f"pi_demo_{charge.idempotency_key}"
        )

    def verify_webhook(self, payload: bytes, signature: str, _now: datetime) -> PaymentEvent:
        values = [value for name, value in signature_fields(signature) if name == "v1"]
        if values != ["fake"]:
            raise BadRequest(INVALID_SIGNATURE)
        return payment_event_of(as_mapping(json.loads(payload)))

    def attach_demo_card(self, customer_id: str) -> str:
        stored = self.store.customers.setdefault(customer_id, StoredCustomer())
        last4 = f"{len(stored.cards) + 1:04d}"
        pm_id = f"pm_demo_{customer_id}_{last4}"
        stored.cards[pm_id] = Card(
            brand="visa",
            cardholder_name="Demo Card",
            exp_month=12,
            exp_year=2035,
            last4=last4,
            payment_method_id=pm_id,
        )
        return pm_id

    def _url(self, session_id: str) -> str:
        return f"{self.public_base_url}/api/app/demo/checkout/{session_id}"


def checkout_page_html(session_id: str, session: StoredSession) -> str:
    heading = (
        "Add a card"
        if session.mode == SETUP_MODE
        else f"Pay {format_price(session.amount_micro)}"
        if session.amount_micro is not None
        else "Pay"
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f"<title>txtlocal demo checkout</title></head><body><h1>{heading}</h1>"
        f'<form action="/api/app/demo/checkout/{session_id}" method="post">'
        '<button type="submit">Pay</button></form></body></html>'
    )


def demo_event_body(
    event_id: str, session_id: str, session: StoredSession, gateway: FakePaymentGateway
) -> dict[str, object]:
    if session.mode == SETUP_MODE:
        payment_method_id = gateway.attach_demo_card(session.customer_id)
        return {
            "id": event_id,
            "type": "setup_intent.succeeded",
            "data": {
                "object": {
                    "id": f"seti_demo_{session_id}",
                    "customer": session.customer_id,
                    "payment_method": payment_method_id,
                }
            },
        }
    invoice_url = f"{gateway.public_base_url}/api/app/demo/invoice/{session_id}"
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": session_id,
                "customer": session.customer_id,
                "invoice": {"hosted_invoice_url": invoice_url, "number": f"DEMO-{session_id[-8:]}"},
                "metadata": {"accountId": session.account_id, "topUpId": session.top_up_id},
            }
        },
    }


def build_demo_router(gateway: FakePaymentGateway, webhook: Webhook) -> APIRouter:
    router = APIRouter(prefix="/api/app/demo")

    @router.get("/checkout/{session_id}")
    async def checkout_page(session_id: str) -> Response:
        session = gateway.store.sessions.get(session_id)
        if session is None:
            return HTMLResponse(DEMO_NOT_FOUND, status_code=HTTPStatus.NOT_FOUND)
        return HTMLResponse(checkout_page_html(session_id, session))

    @router.post("/checkout/{session_id}")
    async def pay(session_id: str) -> Response:
        session = gateway.store.sessions.get(session_id)
        if session is None:
            return HTMLResponse(DEMO_NOT_FOUND, status_code=HTTPStatus.NOT_FOUND)

        event_id = f"evt_demo_{session_id}"
        body = json.dumps(demo_event_body(event_id, session_id, session, gateway)).encode()
        signature = f"t={int(gateway.clock().timestamp())},v1=fake"
        await webhook.handle(body, signature)
        return RedirectResponse(session.success_url, status_code=HTTPStatus.FOUND)

    return router

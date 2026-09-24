import hmac
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from http import HTTPStatus
from typing import Protocol, cast

import httpx

from txtlocal.shared.errors import BadRequest, Upstream
from txtlocal.shared.money import MICRO_PER_PENCE, Micro, micro_to_pence

CONNECT_TIMEOUT_SECONDS = 5.0
TOTAL_TIMEOUT_SECONDS = 30.0
SIGNATURE_TOLERANCE_SECONDS = 300
STRIPE_API = "https://api.stripe.com/v1"

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
class Invoice:
    number: str | None
    url: str | None


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
    invoice_id: str | None = None
    invoice_number: str | None = None
    invoice_url: str | None = None
    kind: str | None = None
    mode: str | None = None
    payment_method_id: str | None = None
    provider_ref: str | None = None
    top_up_id: str | None = None


class PaymentGateway(Protocol):
    async def ensure_customer(self, account_id: str, email: str) -> str: ...

    async def customer_exists(self, customer_id: str) -> bool: ...

    async def checkout(
        self, customer_id: str, pack: Pack, urls: ReturnUrls, idempotency_key: str
    ) -> CheckoutSession: ...

    async def setup_session(self, customer_id: str, urls: ReturnUrls) -> CheckoutSession: ...

    async def payment_methods(self, customer_id: str) -> list[Card]: ...

    async def set_default(self, customer_id: str, payment_method_id: str) -> None: ...

    async def detach(self, payment_method_id: str) -> None: ...

    async def charge_off_session(self, charge: OffSessionCharge) -> ChargeOutcome: ...

    async def invoice(self, invoice_id: str) -> Invoice: ...

    def verify_webhook(self, payload: bytes, signature: str, now: datetime) -> PaymentEvent: ...


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

    return PaymentEvent(
        event_id=string_field(body, "id") or "",
        event_type=string_field(body, "type") or "",
        account_id=string_field(metadata, "accountId"),
        amount_micro=amount_micro_of(fields),
        customer_id=string_field(fields, "customer"),
        invoice_id=string_field(fields, "invoice"),
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

    async def customer_exists(self, customer_id: str) -> bool:
        return await self._customer(customer_id) is not None

    async def payment_methods(self, customer_id: str) -> list[Card]:
        customer = await self._customer(customer_id)
        if customer is None:
            return []

        default_id = default_payment_method_of(customer)
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

    async def invoice(self, invoice_id: str) -> Invoice:
        response = await self._get(f"/invoices/{invoice_id}")
        return Invoice(
            number=string_field(response, "number"),
            url=string_field(response, "hosted_invoice_url"),
        )

    def verify_webhook(self, payload: bytes, signature: str, now: datetime) -> PaymentEvent:
        if not self._signature_valid(payload, signature, now):
            raise BadRequest(INVALID_SIGNATURE)
        return payment_event_of(as_mapping(json.loads(payload)))

    def _signature_valid(self, payload: bytes, signature: str, now: datetime) -> bool:
        if not self.webhook_secret:
            return False

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
        customer = await self._customer(customer_id)
        return None if customer is None else default_payment_method_of(customer)

    async def _customer(self, customer_id: str) -> Mapping[str, object] | None:
        response = await self._request("GET", f"/customers/{customer_id}", None, None)
        if response.status_code == HTTPStatus.NOT_FOUND:
            return None
        if not response.is_success:
            raise stripe_upstream_error(response)

        customer = as_mapping(response.json())
        return None if customer.get("deleted") is True else customer

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


def default_payment_method_of(customer: Mapping[str, object]) -> str | None:
    return string_field(as_mapping(customer.get("invoice_settings")), "default_payment_method")


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

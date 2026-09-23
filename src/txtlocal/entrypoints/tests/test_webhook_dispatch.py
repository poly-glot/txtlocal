import hmac
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING

import httpx
import pytest

from txtlocal.entrypoints.webhook_dispatch import WebhookDispatch, signature_header
from txtlocal.shared.errors import Upstream
from txtlocal.slices.automation.model import WebhookJob

if TYPE_CHECKING:
    from txtlocal.shared.bus import SqsEvent

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
SECRET = "shh-secret"


def verified(secret: str, header: str, body: bytes, now: float) -> bool:
    fields = dict(part.split("=", 1) for part in header.split(","))
    fresh = abs(now - int(fields["t"])) <= 300
    expected = hmac.new(secret.encode(), f"{fields['t']}.".encode() + body, sha256).hexdigest()
    return fresh and hmac.compare_digest(expected, fields["v1"])


def job(
    body: str = '{"event":"message.delivered"}', url: str = "https://example.com/hook"
) -> WebhookJob:
    return WebhookJob(body=body, event="message.delivered", secret=SECRET, url=url)


def dispatch(handler: Callable[[httpx.Request], httpx.Response]) -> WebhookDispatch:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return WebhookDispatch(clock=lambda: NOW, http=http)


def test_signature_header_matches_the_specs_verification_example() -> None:
    body = b'{"a":1}'
    header = signature_header(SECRET, body, 1758283204)

    expected = hmac.new(SECRET.encode(), b"1758283204." + body, sha256).hexdigest()
    assert header == f"t=1758283204,v1={expected}"
    assert verified(SECRET, header, body, now=1758283204)


def test_signature_header_fails_verification_with_the_wrong_secret() -> None:
    header = signature_header(SECRET, b"body", 1758283204)

    assert not verified("a-different-secret", header, b"body", now=1758283204)


async def test_handle_body_posts_a_signature_the_receiver_can_verify() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200)

    await dispatch(handler).handle_body(job().model_dump_json())

    [request] = captured
    assert request.headers["X-Txtlocal-Event"] == "message.delivered"
    assert request.headers["Content-Type"] == "application/json"
    assert verified(
        SECRET, request.headers["X-Txtlocal-Signature"], request.content, now=NOW.timestamp()
    )


@pytest.mark.parametrize("status", [400, 500], ids=["client-error", "server-error"])
async def test_handle_body_raises_upstream_on_a_non_2xx_response(status: int) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(status)

    with pytest.raises(Upstream):
        await dispatch(handler).handle_body(job().model_dump_json())


async def test_handle_body_raises_upstream_on_a_transport_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("boom")

    with pytest.raises(Upstream):
        await dispatch(handler).handle_body(job().model_dump_json())


async def test_handle_sqs_reports_the_failed_job_and_consumes_the_rest() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500 if b"bad" in request.content else 200)

    jobs = [job(body='{"bad":true}') if index == 3 else job() for index in range(5)]
    event: SqsEvent = {
        "Records": [
            {"body": one.model_dump_json(), "messageId": f"sqs-{index}"}
            for index, one in enumerate(jobs)
        ]
    }

    response = await dispatch(handler).handle_sqs(event)

    assert response == {"batchItemFailures": [{"itemIdentifier": "sqs-3"}]}


async def test_handle_sqs_consumes_a_clean_batch() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200)

    event: SqsEvent = {
        "Records": [
            {"body": job().model_dump_json(), "messageId": f"sqs-{index}"} for index in range(3)
        ]
    }

    response = await dispatch(handler).handle_sqs(event)

    assert response == {"batchItemFailures": []}

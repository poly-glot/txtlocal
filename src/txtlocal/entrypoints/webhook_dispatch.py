import hmac
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING

import httpx

from txtlocal.shared import runtime, telemetry
from txtlocal.shared.bus import BatchResponse, SqsEvent, partial_batch
from txtlocal.shared.errors import Upstream
from txtlocal.slices.automation.model import WebhookJob

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock

CONNECT_TIMEOUT_SECONDS = 5.0
CONTENT_TYPE = "application/json"
EVENT_HEADER = "X-Txtlocal-Event"
SIGNATURE_HEADER = "X-Txtlocal-Signature"
TOTAL_TIMEOUT_SECONDS = 10.0


def signature_header(secret: str, body: bytes, now: int) -> str:
    digest = hmac.new(secret.encode(), f"{now}.".encode() + body, sha256).hexdigest()
    return f"t={now},v1={digest}"


@dataclass(frozen=True, slots=True)
class WebhookDispatch:
    clock: Clock
    http: httpx.AsyncClient

    async def handle_body(self, body: str) -> None:
        job = WebhookJob.model_validate_json(body)
        payload = job.body.encode()
        now = int(self.clock().timestamp())

        try:
            response = await self.http.post(
                job.url,
                content=payload,
                headers={
                    "Content-Type": CONTENT_TYPE,
                    EVENT_HEADER: job.event,
                    SIGNATURE_HEADER: signature_header(job.secret, payload, now),
                },
                timeout=httpx.Timeout(TOTAL_TIMEOUT_SECONDS, connect=CONNECT_TIMEOUT_SECONDS),
            )
        except httpx.HTTPError as error:
            raise Upstream(f"webhook POST to {job.url} failed: {error}") from error

        if not response.is_success:
            raise Upstream(f"webhook POST to {job.url} answered {response.status_code}")

    async def handle_sqs(self, event: SqsEvent) -> BatchResponse:
        return await partial_batch(event, self.handle_body, "webhook_dispatch_failed")


from txtlocal.entrypoints import wiring


def handler(event: SqsEvent, _context: object) -> BatchResponse:
    return runtime.run(wiring.webhook_dispatch().handle_sqs(event))


telemetry.configure()

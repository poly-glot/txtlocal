import base64
from dataclasses import dataclass
from datetime import datetime
from email import message_from_bytes
from email.message import EmailMessage
from email.policy import default as default_policy
from typing import TYPE_CHECKING, Protocol, TypedDict

from pydantic import Field

from txtlocal.entrypoints import wiring
from txtlocal.shared import runtime, telemetry
from txtlocal.shared.clock import utc_now
from txtlocal.shared.model import Model

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock

SUBJECT_HEADER = "Subject"


class SesCommonHeaders(Model):
    subject: str = ""


class SesMail(Model):
    common_headers: SesCommonHeaders = Field(default_factory=SesCommonHeaders)
    destination: list[str]
    source: str


class SesNotification(Model):
    content: str | None = None
    mail: SesMail


class SnsNotification(TypedDict):
    Message: str


class SnsRecord(TypedDict):
    Sns: SnsNotification


class SnsEvent(TypedDict):
    Records: list[SnsRecord]


@dataclass(frozen=True, slots=True)
class InboundEmail:
    body: str
    numbers: list[str]
    sender_email: str


class Automation(Protocol):
    async def handle_inbound_email(self, email: InboundEmail, now: datetime) -> None: ...


def mime_of(notification: SesNotification) -> EmailMessage | None:
    if notification.content is None:
        return None

    raw = base64.b64decode(notification.content)
    return message_from_bytes(raw, EmailMessage, policy=default_policy)


def subject_of(notification: SesNotification, mime: EmailMessage | None) -> str:
    header = mime.get(SUBJECT_HEADER) if mime is not None else None
    return str(header) if header is not None else notification.mail.common_headers.subject


def body_of(mime: EmailMessage | None) -> str:
    if mime is None:
        return ""

    part = mime.get_body(preferencelist=("plain",))
    return str(part.get_content()).strip() if part is not None else ""


def combined_text(subject: str, body: str) -> str:
    return " ".join(part.strip() for part in (subject, body) if part.strip())


def numbers_of(destinations: list[str]) -> list[str]:
    return [address.partition("@")[0] for address in destinations if "@" in address]


def inbound_email_of(notification: SesNotification) -> InboundEmail:
    mime = mime_of(notification)
    return InboundEmail(
        body=combined_text(subject_of(notification, mime), body_of(mime)),
        numbers=numbers_of(notification.mail.destination),
        sender_email=notification.mail.source,
    )


@dataclass(frozen=True, slots=True)
class EmailInbound:
    automation: Automation
    clock: Clock

    async def handle_body(self, body: str) -> None:
        notification = SesNotification.model_validate_json(body)
        await self.automation.handle_inbound_email(inbound_email_of(notification), self.clock())

    async def handle_sns(self, event: SnsEvent) -> None:
        for record in event["Records"]:
            await self.handle_body(record["Sns"]["Message"])


def email_inbound() -> EmailInbound:
    return EmailInbound(automation=wiring.automation(), clock=utc_now)


def handler(event: SnsEvent, _context: object) -> None:
    runtime.run(email_inbound().handle_sns(event))


telemetry.configure()

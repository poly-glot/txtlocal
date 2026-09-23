import base64
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage

import pytest

from txtlocal.entrypoints.email_inbound import (
    EmailInbound,
    InboundEmail,
    SesNotification,
    SnsEvent,
    body_of,
    combined_text,
    inbound_email_of,
    mime_of,
    numbers_of,
    subject_of,
)

NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
SENDER_EMAIL = "jan@example.com"


def mime_content(subject: str = "", body: str = "") -> str:
    message = EmailMessage()
    if subject:
        message["Subject"] = subject
    message["From"] = SENDER_EMAIL
    message["To"] = "1234567890@sms.example.com"
    message.set_content(body)
    return base64.b64encode(message.as_bytes()).decode()


def ses_notification_json(
    *, content: str | None, destination: list[str] | None = None, headers_subject: str = ""
) -> str:
    return json.dumps(
        {
            "content": content,
            "mail": {
                "commonHeaders": {"subject": headers_subject},
                "destination": destination or ["1234567890@sms.example.com"],
                "source": SENDER_EMAIL,
            },
        }
    )


@dataclass(slots=True)
class FakeAutomation:
    calls: list[tuple[InboundEmail, datetime]] = field(default_factory=list)

    async def handle_inbound_email(self, email: InboundEmail, now: datetime) -> None:
        self.calls.append((email, now))


def handler_over(automation: FakeAutomation) -> EmailInbound:
    return EmailInbound(automation=automation, clock=lambda: NOW)


@pytest.mark.parametrize(
    ("subject", "body", "expected"),
    [
        ("Re: Sales Report", "Please call me back", "Re: Sales Report Please call me back"),
        ("Re: Sales Report", "", "Re: Sales Report"),
        ("", "Please call me back", "Please call me back"),
        ("", "", ""),
        ("  ", "  ", ""),
    ],
    ids=["subject-and-body", "subject-only", "body-only", "neither", "blank-both"],
)
def test_combined_text(subject: str, body: str, expected: str) -> None:
    assert combined_text(subject, body) == expected


@pytest.mark.parametrize(
    ("destinations", "expected"),
    [
        (["1234567890@sms.example.com"], ["1234567890"]),
        (
            ["1234567890@sms.example.com", "0987654321@sms.example.com"],
            ["1234567890", "0987654321"],
        ),
        (["not-an-address"], []),
        ([], []),
    ],
    ids=["single", "multiple", "missing-at-sign", "empty"],
)
def test_numbers_of(destinations: list[str], expected: list[str]) -> None:
    assert numbers_of(destinations) == expected


def test_mime_of_is_none_without_content() -> None:
    notification = SesNotification.model_validate_json(ses_notification_json(content=None))

    assert mime_of(notification) is None


def test_body_of_extracts_the_plain_text_part() -> None:
    notification = SesNotification.model_validate_json(
        ses_notification_json(content=mime_content(subject="Hi", body="Call me back"))
    )

    assert body_of(mime_of(notification)) == "Call me back"


def test_subject_of_prefers_the_mime_header() -> None:
    notification = SesNotification.model_validate_json(
        ses_notification_json(
            content=mime_content(subject="From the email", body="hi"),
            headers_subject="From common headers",
        )
    )

    assert subject_of(notification, mime_of(notification)) == "From the email"


def test_subject_of_falls_back_to_common_headers_without_content() -> None:
    notification = SesNotification.model_validate_json(
        ses_notification_json(content=None, headers_subject="From common headers")
    )

    assert subject_of(notification, mime_of(notification)) == "From common headers"


def test_inbound_email_of_combines_subject_body_and_destinations() -> None:
    notification = SesNotification.model_validate_json(
        ses_notification_json(
            content=mime_content(subject="Re: Sales Report", body="Please call me back"),
            destination=["1234567890@sms.example.com", "0987654321@sms.example.com"],
        )
    )

    email = inbound_email_of(notification)

    assert email.sender_email == SENDER_EMAIL
    assert email.numbers == ["1234567890", "0987654321"]
    assert email.body == "Re: Sales Report Please call me back"


async def test_handle_body_calls_automation_with_the_parsed_email() -> None:
    automation = FakeAutomation()
    handler = handler_over(automation)

    await handler.handle_body(
        ses_notification_json(content=mime_content(subject="Hi", body="Call me"))
    )

    [(email, now)] = automation.calls
    assert (email.sender_email, email.numbers, now) == (SENDER_EMAIL, ["1234567890"], NOW)


async def test_handle_sns_processes_every_record() -> None:
    automation = FakeAutomation()
    handler = handler_over(automation)
    event: SnsEvent = {
        "Records": [
            {"Sns": {"Message": ses_notification_json(content=mime_content(body="first"))}},
            {"Sns": {"Message": ses_notification_json(content=mime_content(body="second"))}},
        ]
    }

    await handler.handle_sns(event)

    assert [email.body for email, _now in automation.calls] == ["first", "second"]

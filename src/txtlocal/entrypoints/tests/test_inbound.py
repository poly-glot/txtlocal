import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from txtlocal.entrypoints.inbound import (
    Inbound,
    SnsEvent,
    first_word,
    is_opt_out_keyword,
)
from txtlocal.shared.errors import Internal
from txtlocal.shared.phone import E164
from txtlocal.slices.messaging.model import InboundMessage, MessageRef

ACCOUNT = "account-1"
CAMPAIGN = "campaign-1"
DESTINATION = E164("+447984390718")
MESSAGE_ID = "message-1"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
PEER = E164("+447411972333")
PREVIOUS_ID = "provider-1"
SENDER_ID = "sender-1"


def provider_inbound_json(
    body: str = "hello",
    previous_id: str | None = PREVIOUS_ID,
    keyword: str | None = None,
    inbound_id: str = "inbound-1",
) -> str:
    return json.dumps(
        {
            "destinationNumber": DESTINATION,
            "inboundMessageId": inbound_id,
            "messageBody": body,
            "messageKeyword": keyword,
            "originationNumber": PEER,
            "previousPublishedMessageId": previous_id,
        }
    )


def ref() -> MessageRef:
    return MessageRef(
        account_id=ACCOUNT,
        campaign_id=CAMPAIGN,
        message_id=MESSAGE_ID,
        peer=PEER,
        sender_id=SENDER_ID,
    )


@dataclass(slots=True)
class FakeMessaging:
    found: MessageRef | None = None
    recorded: list[tuple[str, InboundMessage, datetime]] = field(default_factory=list)
    marked: set[str] = field(default_factory=set)

    async def find_by_provider_id(self, provider_message_id: str) -> MessageRef | None:
        del provider_message_id
        return self.found

    async def record_inbound(self, account_id: str, inbound: InboundMessage, now: datetime) -> bool:
        if inbound.inbound_message_id in self.marked:
            return False

        self.marked.add(inbound.inbound_message_id)
        self.recorded.append((account_id, inbound, now))
        return True


@dataclass(slots=True)
class FakeContacts:
    failures: int = 0
    opted_out: list[tuple[str, str, datetime]] = field(default_factory=list)

    async def opt_out(self, account_id: str, mobile: str, now: datetime) -> None:
        if self.failures:
            self.failures -= 1
            raise Internal("ProvisionedThroughputExceededException")

        self.opted_out.append((account_id, mobile, now))


@dataclass(slots=True)
class FakeAutomation:
    calls: list[tuple[str, InboundMessage, datetime]] = field(default_factory=list)

    async def run_inbound(
        self, account_id: str, inbound: InboundMessage, now: datetime
    ) -> list[object]:
        self.calls.append((account_id, inbound, now))
        return []


@dataclass(slots=True)
class FakeInbox:
    noted: list[tuple[str, InboundMessage, str | None, datetime]] = field(default_factory=list)

    async def note_inbound(
        self, account_id: str, inbound: InboundMessage, sender_id: str | None, now: datetime
    ) -> None:
        self.noted.append((account_id, inbound, sender_id, now))


def handler_over(
    messaging: FakeMessaging,
    *,
    automation: FakeAutomation | None = None,
    contacts: FakeContacts | None = None,
    inbox: FakeInbox | None = None,
) -> Inbound:
    return Inbound(
        automation=automation or FakeAutomation(),
        clock=lambda: NOW,
        contacts=contacts or FakeContacts(),
        inbox=inbox or FakeInbox(),
        messaging=messaging,
    )


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("stop", True),
        ("STOP", True),
        ("Stop now please", True),
        ("stopall", True),
        ("unsubscribe", True),
        ("cancel", True),
        ("end", True),
        ("quit", True),
        ("stopping", False),
        ("hello", False),
        ("", False),
        ("   ", False),
    ],
    ids=[
        "lowercase",
        "uppercase",
        "first-word-of-a-sentence",
        "stopall",
        "unsubscribe",
        "cancel",
        "end",
        "quit",
        "not-an-exact-word-match",
        "not-a-keyword",
        "empty",
        "blank",
    ],
)
def test_is_opt_out_keyword(body: str, expected: bool) -> None:
    assert is_opt_out_keyword(body) is expected


@pytest.mark.parametrize(
    ("body", "expected"),
    [("hello there", "hello"), ("  hi  ", "hi"), ("", "")],
    ids=["first-of-two-words", "surrounding-whitespace-stripped", "empty-body"],
)
def test_first_word(body: str, expected: str) -> None:
    assert first_word(body) == expected


async def test_handle_body_without_a_previous_id_is_unattributed() -> None:
    messaging = FakeMessaging(found=ref())
    contacts = FakeContacts()
    automation = FakeAutomation()
    inbox = FakeInbox()
    handler = handler_over(messaging, automation=automation, contacts=contacts, inbox=inbox)

    await handler.handle_body(provider_inbound_json(previous_id=None))

    assert messaging.recorded == []
    assert contacts.opted_out == []
    assert automation.calls == []
    assert inbox.noted == []


async def test_handle_body_unattributed_when_the_lookup_misses() -> None:
    messaging = FakeMessaging(found=None)
    inbox = FakeInbox()
    handler = handler_over(messaging, inbox=inbox)

    await handler.handle_body(provider_inbound_json())

    assert inbox.noted == []


async def test_a_redelivered_message_runs_automation_and_the_inbox_once() -> None:
    messaging = FakeMessaging(found=ref())
    automation = FakeAutomation()
    inbox = FakeInbox()
    handler = handler_over(messaging, automation=automation, inbox=inbox)

    await handler.handle_body(provider_inbound_json(body="hello"))
    await handler.handle_body(provider_inbound_json(body="hello"))

    assert (len(automation.calls), len(inbox.noted)) == (1, 1)


async def test_a_stop_whose_opt_out_failed_is_applied_on_the_redelivery() -> None:
    messaging = FakeMessaging(found=ref())
    contacts = FakeContacts(failures=1)
    handler = handler_over(messaging, contacts=contacts)

    with pytest.raises(Internal):
        await handler.handle_body(provider_inbound_json(body="STOP"))
    await handler.handle_body(provider_inbound_json(body="STOP"))

    assert contacts.opted_out == [(ACCOUNT, PEER, NOW)]


async def test_a_stop_whose_opt_out_failed_records_no_dedupe_marker() -> None:
    messaging = FakeMessaging(found=ref())
    handler = handler_over(messaging, contacts=FakeContacts(failures=1))

    with pytest.raises(Internal):
        await handler.handle_body(provider_inbound_json(body="STOP"))

    assert messaging.recorded == []


async def test_handle_body_opt_out_keyword_opts_the_peer_out() -> None:
    messaging = FakeMessaging(found=ref())
    contacts = FakeContacts()
    handler = handler_over(messaging, contacts=contacts)

    await handler.handle_body(provider_inbound_json(body="STOP"))

    assert contacts.opted_out == [(ACCOUNT, PEER, NOW)]


async def test_handle_body_non_opt_out_keyword_does_not_opt_out() -> None:
    messaging = FakeMessaging(found=ref())
    contacts = FakeContacts()
    handler = handler_over(messaging, contacts=contacts)

    await handler.handle_body(provider_inbound_json(body="hello"))

    assert contacts.opted_out == []


async def test_handle_body_runs_automation_and_notes_inbound_with_the_refs_sender() -> None:
    messaging = FakeMessaging(found=ref())
    automation = FakeAutomation()
    inbox = FakeInbox()
    handler = handler_over(messaging, automation=automation, inbox=inbox)

    await handler.handle_body(provider_inbound_json(body="hello"))

    [(automation_account, inbound, automation_now)] = automation.calls
    assert (automation_account, inbound.peer, inbound.body, automation_now) == (
        ACCOUNT,
        PEER,
        "hello",
        NOW,
    )
    [(inbox_account, noted_inbound, sender_id, inbox_now)] = inbox.noted
    assert (inbox_account, sender_id, inbox_now) == (ACCOUNT, SENDER_ID, NOW)
    assert noted_inbound == inbound


async def test_handle_sns_processes_every_record() -> None:
    messaging = FakeMessaging(found=ref())
    inbox = FakeInbox()
    handler = handler_over(messaging, inbox=inbox)
    event: SnsEvent = {
        "Records": [
            {"Sns": {"Message": provider_inbound_json(body="hello")}},
            {"Sns": {"Message": provider_inbound_json(body="hi again", inbound_id="inbound-2")}},
        ]
    }

    await handler.handle_sns(event)

    assert [row.body for (_, row, _, _) in inbox.noted] == ["hello", "hi again"]

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, TypedDict

from txtlocal.shared import runtime, telemetry
from txtlocal.slices.inbox.model import ProviderInboundSms
from txtlocal.slices.messaging.model import InboundMessage, MessageRef

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock
    from txtlocal.shared.phone import E164

STOP_KEYWORDS = frozenset({"CANCEL", "END", "QUIT", "STOP", "STOPALL", "UNSUBSCRIBE"})


class Messaging(Protocol):
    async def record_inbound(
        self, account_id: str, inbound: InboundMessage, now: datetime
    ) -> bool: ...

    async def find_by_provider_id(self, provider_message_id: str) -> MessageRef | None: ...


class Contacts(Protocol):
    async def opt_out(self, account_id: str, mobile: E164, now: datetime) -> None: ...


class Automation(Protocol):
    async def run_inbound(
        self, account_id: str, inbound: InboundMessage, now: datetime
    ) -> object: ...


class Inbox(Protocol):
    async def note_inbound(
        self, account_id: str, inbound: InboundMessage, sender_id: str | None, now: datetime
    ) -> None: ...


class SnsNotification(TypedDict):
    Message: str


class SnsRecord(TypedDict):
    Sns: SnsNotification


class SnsEvent(TypedDict):
    Records: list[SnsRecord]


def first_word(body: str) -> str:
    stripped = body.strip()
    return stripped.split(maxsplit=1)[0] if stripped else ""


def is_opt_out_keyword(body: str) -> bool:
    return first_word(body).upper() in STOP_KEYWORDS


def inbound_message_of(provider: ProviderInboundSms, now: datetime) -> InboundMessage:
    return InboundMessage(
        body=provider.message_body,
        destination=provider.destination_number,
        inbound_message_id=provider.inbound_message_id,
        keyword=provider.message_keyword or "",
        peer=provider.origination_number,
        previous_published_message_id=provider.previous_published_message_id,
        received_at=now,
    )


@dataclass(frozen=True, slots=True)
class Inbound:
    automation: Automation
    clock: Clock
    contacts: Contacts
    inbox: Inbox
    messaging: Messaging

    async def handle_body(self, body: str) -> None:
        provider = ProviderInboundSms.model_validate_json(body)
        now = self.clock()

        ref = (
            await self.messaging.find_by_provider_id(provider.previous_published_message_id)
            if provider.previous_published_message_id is not None
            else None
        )
        if ref is None:
            telemetry.log("inbound_message", outcome="unattributed")
            return

        inbound = inbound_message_of(provider, now)

        if is_opt_out_keyword(inbound.body):
            await self.contacts.opt_out(ref.account_id, inbound.peer, now)

        if not await self.messaging.record_inbound(ref.account_id, inbound, now):
            telemetry.log("inbound_message", account_id=ref.account_id, outcome="duplicate")
            return

        await self.automation.run_inbound(ref.account_id, inbound, now)
        await self.inbox.note_inbound(ref.account_id, inbound, ref.sender_id, now)

        telemetry.log(
            "inbound_message",
            account_id=ref.account_id,
            message_id=inbound.inbound_message_id,
            outcome="received",
        )

    async def handle_sns(self, event: SnsEvent) -> None:
        for record in event["Records"]:
            await self.handle_body(record["Sns"]["Message"])


from txtlocal.entrypoints import wiring


def handler(event: SnsEvent, _context: object) -> None:
    runtime.run(wiring.inbound().handle_sns(event))


telemetry.configure()

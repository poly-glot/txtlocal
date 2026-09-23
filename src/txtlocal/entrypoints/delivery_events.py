from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, TypedDict, assert_never

from txtlocal.shared import runtime, telemetry
from txtlocal.slices.messaging.model import MessageStatus, ProviderEvent, Transition

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock


class Messaging(Protocol):
    async def apply_event(self, event: ProviderEvent, now: datetime) -> Transition | None: ...


class Campaigns(Protocol):
    async def record_delivery(
        self, account_id: str, campaign_id: str, *, delivered: bool, now: datetime
    ) -> None: ...


class Automation(Protocol):
    async def on_delivery(self, transition: Transition, now: datetime) -> None: ...


class SnsNotification(TypedDict):
    Message: str


class SnsRecord(TypedDict):
    Sns: SnsNotification


class SnsEvent(TypedDict):
    Records: list[SnsRecord]


def delivery_of(status: MessageStatus) -> bool | None:
    match status:
        case MessageStatus.DELIVERED:
            return True
        case MessageStatus.FAILED:
            return False
        case MessageStatus.QUEUED | MessageStatus.RECEIVED | MessageStatus.SENT:
            return None
        case _:
            assert_never(status)


@dataclass(frozen=True, slots=True)
class DeliveryEvents:
    campaigns: Campaigns
    clock: Clock
    messaging: Messaging
    automation: Automation | None = None

    async def handle_body(self, body: str) -> None:
        event = ProviderEvent.model_validate_json(body)
        now = self.clock()

        transition = await self.messaging.apply_event(event, now)
        if transition is None:
            telemetry.log(
                "delivery_event",
                event_type=event.event_type,
                outcome="ignored",
                provider_message_id=event.message_id,
            )
            return

        delivered = delivery_of(transition.status)
        if delivered is not None:
            await self.campaigns.record_delivery(
                transition.account_id, transition.campaign_id, delivered=delivered, now=now
            )

        if self.automation is not None:
            await self.automation.on_delivery(transition, now)

        telemetry.log(
            "delivery_event",
            account_id=transition.account_id,
            campaign_id=transition.campaign_id,
            event_type=event.event_type,
            message_id=transition.message_id,
            outcome="applied",
            status=transition.status,
        )

    async def handle_sns(self, event: SnsEvent) -> None:
        for record in event["Records"]:
            await self.handle_body(record["Sns"]["Message"])


from txtlocal.entrypoints import wiring


def handler(event: SnsEvent, _context: object) -> None:
    runtime.run(wiring.delivery_events().handle_sns(event))


telemetry.configure()

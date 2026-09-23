import json
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from txtlocal.entrypoints.delivery_events import DeliveryEvents, SnsEvent, delivery_of
from txtlocal.shared.errors import AppError, Upstream
from txtlocal.slices.messaging.model import MessageStatus, ProviderEvent, Transition

ACCOUNT = "account-1"
CAMPAIGN = "campaign-1"
EVENT_AT = datetime(2026, 9, 19, 11, 59, 58, tzinfo=UTC)
MESSAGE_KEY = "txtlocal#ACCOUNT#account-1|MSG#message-1"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)


def provider_event_json() -> str:
    return json.dumps(
        {
            "context": {"messageKey": MESSAGE_KEY},
            "destinationPhoneNumber": "redacted",
            "eventTimestamp": int(EVENT_AT.timestamp()) * 1000,
            "eventType": "TEXT_DELIVERED",
            "isoCountryCode": "GB",
            "messageId": "provider-1",
            "messageStatus": "DELIVERED",
            "totalMessageParts": 1,
            "totalMessagePrice": 0.0427,
        }
    )


def parsed_provider_event() -> ProviderEvent:
    return ProviderEvent(
        context={"messageKey": MESSAGE_KEY},
        event_timestamp=EVENT_AT,
        event_type="TEXT_DELIVERED",
        message_id="provider-1",
        total_message_parts=1,
        total_message_price=0.0427,
    )


def won(status: MessageStatus) -> Transition:
    return Transition(
        account_id=ACCOUNT,
        campaign_id=CAMPAIGN,
        failure_reason=None,
        message_id="message-1",
        status=status,
    )


@dataclass(slots=True)
class FakeMessaging:
    applied: list[tuple[ProviderEvent, datetime]] = field(default_factory=list)
    transition: Transition | None = None

    async def apply_event(self, event: ProviderEvent, now: datetime) -> Transition | None:
        self.applied.append((event, now))
        return self.transition


@dataclass(slots=True)
class FakeCampaigns:
    deliveries: list[tuple[str, str, bool, datetime]] = field(default_factory=list)

    async def record_delivery(
        self, account_id: str, campaign_id: str, *, delivered: bool, now: datetime
    ) -> None:
        self.deliveries.append((account_id, campaign_id, delivered, now))


@dataclass(slots=True)
class FakeAutomation:
    failure: AppError | None = None
    notified: list[tuple[Transition, datetime]] = field(default_factory=list)

    async def on_delivery(self, transition: Transition, now: datetime) -> None:
        if self.failure is not None:
            raise self.failure

        self.notified.append((transition, now))


def events_over(
    messaging: FakeMessaging, campaigns: FakeCampaigns, automation: FakeAutomation | None = None
) -> DeliveryEvents:
    return DeliveryEvents(
        automation=automation, campaigns=campaigns, clock=lambda: NOW, messaging=messaging
    )


@pytest.mark.parametrize(
    ("status", "delivered"),
    [
        (MessageStatus.DELIVERED, True),
        (MessageStatus.FAILED, False),
        (MessageStatus.QUEUED, None),
        (MessageStatus.RECEIVED, None),
        (MessageStatus.SENT, None),
    ],
    ids=[
        "delivered-counts-delivered",
        "failed-counts-undelivered",
        "queued-is-not-a-delivery",
        "received-is-not-a-delivery",
        "sent-is-not-a-delivery",
    ],
)
def test_delivery_of(status: MessageStatus, delivered: bool | None) -> None:
    assert delivery_of(status) is delivered


@pytest.mark.parametrize(
    ("transition", "deliveries"),
    [
        (won(MessageStatus.DELIVERED), [(ACCOUNT, CAMPAIGN, True, NOW)]),
        (won(MessageStatus.FAILED), [(ACCOUNT, CAMPAIGN, False, NOW)]),
        (won(MessageStatus.SENT), []),
        (None, []),
    ],
    ids=["delivered", "failed", "sent-records-nothing", "lost-records-nothing"],
)
async def test_handle_body_records_a_won_delivery(
    transition: Transition | None, deliveries: list[tuple[str, str, bool, datetime]]
) -> None:
    campaigns = FakeCampaigns()
    events = events_over(FakeMessaging(transition=transition), campaigns)

    await events.handle_body(provider_event_json())

    assert campaigns.deliveries == deliveries


@pytest.mark.parametrize(
    ("transition", "notified"),
    [
        (won(MessageStatus.DELIVERED), [(won(MessageStatus.DELIVERED), NOW)]),
        (won(MessageStatus.SENT), [(won(MessageStatus.SENT), NOW)]),
        (None, []),
    ],
    ids=[
        "delivered-notifies-automation",
        "sent-still-notifies-automation",
        "lost-does-not-notify-automation",
    ],
)
async def test_handle_body_notifies_automation_on_every_won_transition(
    transition: Transition | None, notified: list[tuple[Transition, datetime]]
) -> None:
    automation = FakeAutomation()
    events = events_over(FakeMessaging(transition=transition), FakeCampaigns(), automation)

    await events.handle_body(provider_event_json())

    assert automation.notified == notified


async def test_handle_sns_applies_the_record_message_at_now() -> None:
    messaging = FakeMessaging()
    event: SnsEvent = {"Records": [{"Sns": {"Message": provider_event_json()}}]}

    await events_over(messaging, FakeCampaigns()).handle_sns(event)

    assert messaging.applied == [(parsed_provider_event(), NOW)]


async def test_handle_body_records_the_delivery_before_notifying_automation() -> None:
    campaigns = FakeCampaigns()
    automation = FakeAutomation(failure=Upstream("webhooks queue unavailable"))
    events = events_over(
        FakeMessaging(transition=won(MessageStatus.DELIVERED)), campaigns, automation
    )

    with pytest.raises(Upstream):
        await events.handle_body(provider_event_json())

    assert campaigns.deliveries == [(ACCOUNT, CAMPAIGN, True, NOW)]

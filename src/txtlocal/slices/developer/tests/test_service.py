from datetime import timedelta

import pytest

from txtlocal.shared.errors import BadRequest, Forbidden, NotFound, PaymentRequired
from txtlocal.shared.money import Micro
from txtlocal.slices.contacts.model import ContactList
from txtlocal.slices.developer.model import (
    MAX_CUSTOM_STRING,
    MAX_MESSAGES,
    MAX_MMS_BODY,
    MAX_SUBJECT,
    V3ContactInput,
    V3HistoryQuery,
    V3HistoryStatus,
    V3MmsMessage,
    V3SendMessage,
    V3SendRequest,
)
from txtlocal.slices.developer.repo import LogRows
from txtlocal.slices.developer.service import (
    MESSAGES_COUNT_MESSAGE,
    DeveloperService,
    checked_custom_string,
    checked_mms_message,
    checked_schedule,
)
from txtlocal.slices.developer.tests.fakes import (
    ACCOUNT_ID,
    NOW,
    PRINCIPAL,
    USER_ID,
    FakeAccounts,
    FakeBilling,
    FakeCampaigns,
    FakeContacts,
    FakeLogQueries,
    FakeMessaging,
    FakeRepo,
    FakeSenders,
    FakeSettings,
    gateway,
)
from txtlocal.slices.identity.model import Account
from txtlocal.slices.messaging.model import Direction, MessageRow, MessageStatus, Product
from txtlocal.slices.messaging.policy import SendPolicy
from txtlocal.slices.senders.model import Channel, Sender, SenderKind, SenderStatus

ACCOUNT = Account(
    account_id=ACCOUNT_ID,
    created_at=NOW,
    email="owner@example.com",
    name="Acme",
    pricing_country="GB",
)
SHARED_SENDER = Sender(
    capabilities=(Channel.SMS,),
    country="GB",
    created_at=NOW,
    kind=SenderKind.SHARED,
    sender_id="snd_shared",
    status=SenderStatus.READY,
    value="SHARED",
)
POLICY = SendPolicy(
    allowed_countries=frozenset({"GB"}), daily_cap=500, max_price_usd="0.10", sandbox=False
)
OUTBOUND_ROW = MessageRow(
    account_id=ACCOUNT_ID,
    body="out",
    campaign_id="cmp_1",
    country="GB",
    direction=Direction.OUT,
    encoding="GSM7",
    from_="snd_shared",
    kind=Product.SMS,
    message_id="msg_out",
    parts=1,
    price_micro=Micro(4_270),
    queued_at=NOW,
    status=MessageStatus.QUEUED,
    to="+447400123123",
    user_id=USER_ID,
    username="dev@example.com",
)
INBOUND_ROW = MessageRow(
    account_id=ACCOUNT_ID,
    body="in",
    campaign_id="",
    country="GB",
    direction=Direction.IN,
    encoding="GSM7",
    from_="+447400123123",
    kind=Product.SMS,
    message_id="msg_in",
    parts=1,
    price_micro=Micro(0),
    queued_at=NOW,
    status=MessageStatus.RECEIVED,
    to="+447908661626",
    user_id="",
    username="",
)


def build_service(
    *,
    billing: FakeBilling | None = None,
    campaigns: FakeCampaigns | None = None,
    contacts: FakeContacts | None = None,
    messaging: FakeMessaging | None = None,
    repo: FakeRepo | None = None,
    senders: FakeSenders | None = None,
) -> DeveloperService:
    return DeveloperService(
        accounts=FakeAccounts(account=ACCOUNT),
        base_url="https://example.com",
        billing=billing if billing is not None else FakeBilling(),
        campaigns=campaigns if campaigns is not None else FakeCampaigns(),
        clock=lambda: NOW,
        contacts=contacts if contacts is not None else FakeContacts(),
        docs_url="https://example.com/docs",
        gateway=gateway(),
        log_queries=FakeLogQueries(result=LogRows(rows=[])),
        messaging=messaging if messaging is not None else FakeMessaging(),
        policy=POLICY,
        rate_limit_per_minute=60,
        repo=repo if repo is not None else FakeRepo(),
        senders=senders if senders is not None else FakeSenders(sender=SHARED_SENDER),
        settings=FakeSettings(),
    )


def list_named(list_id: str, name: str) -> ContactList:
    return ContactList(created_at=NOW, list_id=list_id, name=name)


@pytest.mark.parametrize(
    ("count", "raises"),
    [(MAX_MESSAGES, False), (MAX_MESSAGES + 1, True)],
    ids=["ceiling-accepted", "ceiling-plus-one-refused"],
)
async def test_send_message_count_ceiling(count: int, raises: bool) -> None:
    service = build_service()
    request = V3SendRequest(
        messages=[V3SendMessage(body="hi", to="+447400123123") for _ in range(count)]
    )

    if raises:
        with pytest.raises(BadRequest) as caught:
            await service.send(PRINCIPAL, request, NOW)
        assert str(caught.value) == MESSAGES_COUNT_MESSAGE
    else:
        response = await service.send(PRINCIPAL, request, NOW)
        assert len(response.messages) == count


@pytest.mark.parametrize(
    ("length", "raises"),
    [(MAX_CUSTOM_STRING, False), (MAX_CUSTOM_STRING + 1, True)],
    ids=["ceiling-accepted", "ceiling-plus-one-refused"],
)
def test_custom_string_ceiling(length: int, raises: bool) -> None:
    value = "a" * length
    if raises:
        with pytest.raises(BadRequest, match=r"messages\[0\]\.customString"):
            checked_custom_string(0, value)
    else:
        checked_custom_string(0, value)


@pytest.mark.parametrize(
    ("length", "raises"),
    [(MAX_MMS_BODY, False), (MAX_MMS_BODY + 1, True)],
    ids=["ceiling-accepted", "ceiling-plus-one-refused"],
)
def test_mms_body_ceiling(length: int, raises: bool) -> None:
    message = V3MmsMessage(
        body="a" * length, media_url="https://example.com/a.jpg", to="+447400123123"
    )
    if raises:
        with pytest.raises(BadRequest, match=r"messages\[0\]\.body"):
            checked_mms_message(0, message, "GB", NOW)
    else:
        checked_mms_message(0, message, "GB", NOW)


def test_mms_subject_ceiling_is_refused_past_forty_characters() -> None:
    message = V3MmsMessage(
        body="hi",
        media_url="https://example.com/a.jpg",
        subject="a" * (MAX_SUBJECT + 1),
        to="+447400123123",
    )
    with pytest.raises(BadRequest, match=r"messages\[0\]\.subject"):
        checked_mms_message(0, message, "GB", NOW)


def test_schedule_in_the_past_is_a_range_error() -> None:
    with pytest.raises(BadRequest, match=r"messages\[0\]\.schedule: must be in the future"):
        checked_schedule(0, NOW, NOW)


def test_schedule_too_far_ahead_is_a_range_error() -> None:
    with pytest.raises(BadRequest, match=r"messages\[0\]\.schedule: must be in the future"):
        checked_schedule(0, NOW + timedelta(days=91), NOW)


def test_schedule_within_range_is_rejected_as_unsupported() -> None:
    with pytest.raises(BadRequest, match=r"scheduling is not available yet"):
        checked_schedule(0, NOW + timedelta(days=1), NOW)


async def test_send_happy_path_dispatches_and_reserves_the_total() -> None:
    billing = FakeBilling(rate_micro=Micro(10_000))
    messaging = FakeMessaging()
    service = build_service(billing=billing, messaging=messaging)
    request = V3SendRequest(
        messages=[
            V3SendMessage(
                body="Your table is ready", custom_string="order-8812", to="+447400123123"
            )
        ]
    )

    response = await service.send(PRINCIPAL, request, NOW)

    assert len(response.messages) == 1
    sent = response.messages[0]
    assert sent.status is MessageStatus.QUEUED
    assert sent.custom_string == "order-8812"
    assert sent.country == "GB"
    assert sent.price == "0.01"
    assert response.total_price == sent.price
    assert len(messaging.dispatched) == 1
    assert billing.reserved[0][0] == ACCOUNT_ID
    assert billing.reserved[0][1] == Micro(10_000)
    assert not billing.settled


async def test_balance_is_a_bare_decimal_with_no_currency_symbol() -> None:
    service = build_service(billing=FakeBilling(balance_micro=100_000_000))

    balance = await service.balance(PRINCIPAL, NOW)

    assert balance.balance == "100.00"
    assert balance.currency == "GBP"


async def test_send_remembers_custom_string_for_later_history_reads() -> None:
    repo = FakeRepo()
    service = build_service(repo=repo)
    request = V3SendRequest(
        messages=[V3SendMessage(body="hi", custom_string="order-1", to="+447400123123")]
    )

    response = await service.send(PRINCIPAL, request, NOW)

    message_id = response.messages[0].message_id
    assert repo.custom_strings[message_id] == "order-1"


async def test_send_refuses_the_whole_batch_and_reserves_nothing_when_country_not_enabled() -> None:
    billing = FakeBilling()
    senders = FakeSenders(sender=SHARED_SENDER, always_ready=True)
    service = build_service(billing=billing, senders=senders)
    request = V3SendRequest(messages=[V3SendMessage(body="hi", to="+12025550123")])

    with pytest.raises(Forbidden):
        await service.send(PRINCIPAL, request, NOW)

    assert billing.reserved == []


async def test_send_insufficient_balance_raises_payment_required() -> None:
    billing = FakeBilling(balance_micro=0)
    service = build_service(billing=billing)
    request = V3SendRequest(messages=[V3SendMessage(body="hi", to="+447400123123")])

    with pytest.raises(PaymentRequired):
        await service.send(PRINCIPAL, request, NOW)


async def test_send_invalid_to_names_the_field_and_index() -> None:
    service = build_service()
    request = V3SendRequest(messages=[V3SendMessage(body="hi", to="not-a-number")])

    with pytest.raises(BadRequest) as caught:
        await service.send(PRINCIPAL, request, NOW)
    assert str(caught.value) == "messages[0].to: must be an E.164 number"


async def test_send_unknown_sender_names_the_field_and_index() -> None:
    us_sender = SHARED_SENDER.model_copy(update={"country": "US"})
    service = build_service(senders=FakeSenders(sender=us_sender))
    request = V3SendRequest(messages=[V3SendMessage(body="hi", to="+447400123123")])

    with pytest.raises(BadRequest) as caught:
        await service.send(PRINCIPAL, request, NOW)
    assert str(caught.value) == "messages[0].from: not a sender you can use for GB"


async def test_send_reuses_the_landing_campaign_across_calls() -> None:
    repo = FakeRepo()
    campaigns = FakeCampaigns()
    messaging = FakeMessaging()
    service = build_service(repo=repo, campaigns=campaigns, messaging=messaging)
    request = V3SendRequest(messages=[V3SendMessage(body="hi", to="+447400123123")])

    await service.send(PRINCIPAL, request, NOW)
    await service.send(PRINCIPAL, request, NOW)

    assert len(campaigns.created) == 1
    assert repo.campaign_ids[ACCOUNT_ID] == campaigns.next_id
    assert all(job.campaign_id == campaigns.next_id for job in messaging.dispatched)


async def test_send_uses_a_pre_existing_landing_campaign_without_creating_a_new_one() -> None:
    repo = FakeRepo()
    repo.campaign_ids[ACCOUNT_ID] = "cmp_already_there"
    campaigns = FakeCampaigns()
    service = build_service(repo=repo, campaigns=campaigns)
    request = V3SendRequest(messages=[V3SendMessage(body="hi", to="+447400123123")])

    await service.send(PRINCIPAL, request, NOW)

    assert campaigns.created == []


async def test_history_filters_by_direction() -> None:
    service = build_service(messaging=FakeMessaging(history_rows=[OUTBOUND_ROW, INBOUND_ROW]))

    page = await service.history(PRINCIPAL, V3HistoryQuery(direction=Direction.IN), NOW)

    assert [one.message_id for one in page.messages] == ["msg_in"]


async def test_history_never_matches_scheduled_or_cancelled_status() -> None:
    service = build_service(messaging=FakeMessaging(history_rows=[OUTBOUND_ROW]))

    page = await service.history(PRINCIPAL, V3HistoryQuery(status=V3HistoryStatus.SCHEDULED), NOW)

    assert page.messages == []


async def test_detail_translates_message_not_found() -> None:
    service = build_service()

    with pytest.raises(NotFound) as caught:
        await service.detail(PRINCIPAL, "msg_missing")
    assert str(caught.value) == "No message with that id"


async def test_remove_contact_translates_missing_list() -> None:
    service = build_service(contacts=FakeContacts())

    with pytest.raises(NotFound) as caught:
        await service.remove_contact(PRINCIPAL, "lst_missing", "+447400123123")
    assert str(caught.value) == "No list with that id"


async def test_remove_contact_translates_missing_contact() -> None:
    contacts = FakeContacts(lists_by_id={"lst_1": list_named("lst_1", "Autumn launch")})
    service = build_service(contacts=contacts)

    with pytest.raises(NotFound) as caught:
        await service.remove_contact(PRINCIPAL, "lst_1", "+447400123123")
    assert str(caught.value) == "No contact with that id"


async def test_add_contact_marks_created_false_for_an_existing_mobile() -> None:
    contacts = FakeContacts(lists_by_id={"lst_1": list_named("lst_1", "Autumn launch")})
    service = build_service(contacts=contacts)
    request = V3ContactInput(first_name="Sam", mobile="+447400123123")

    first = await service.add_contact(PRINCIPAL, "lst_1", request)
    second = await service.add_contact(PRINCIPAL, "lst_1", request)

    assert first.created is True
    assert second.created is False

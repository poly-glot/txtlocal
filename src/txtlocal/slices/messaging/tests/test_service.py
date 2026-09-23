import logging
from datetime import date, datetime, timedelta
from random import Random

import pytest

from txtlocal.shared.errors import BadRequest, Internal, NotFound, RateLimited, Upstream
from txtlocal.shared.phone import E164, INVALID_NUMBER_MESSAGE
from txtlocal.slices.identity.model import MessagingSettings, UnicodeMode
from txtlocal.slices.messaging.gateway import Dispatch, MediaDispatch
from txtlocal.slices.messaging.model import (
    BodyQuote,
    Direction,
    DispatchOutcome,
    HistoryQuery,
    MessageKey,
    MessageRef,
    MessageStatus,
    MessageType,
    Product,
    ProviderEvent,
    RefusalReason,
    SearchField,
    TemplateRequest,
    Transition,
    message_key_for,
    uuid7_at,
)
from txtlocal.slices.messaging.segments import Encoding
from txtlocal.slices.messaging.service import (
    EXPORT_MAX_ROWS,
    EXPORT_TRUNCATED,
    HISTORY_TOO_FAR_BACK,
    INVALID_CURSOR,
    MAX_MEDIA_BYTES,
    MEDIA_NOT_FOUND,
    MEDIA_TOO_LARGE_MESSAGE,
    MEDIA_TYPE_MESSAGE,
    MESSAGE_ACCEPTED,
    MESSAGE_NOT_FOUND,
    MMS_JOB_MISSING_MEDIA,
    MMS_MAX_CHARS,
    MMS_TOO_LONG_MESSAGE,
    PAGE_SIZE,
    RANGE_INVERTED,
    RETENTION_DAYS,
    SPEND_LIMIT,
    STALE_CLAIM,
    TEMPLATE_NOT_FOUND,
    MessagingService,
    status_of_event,
)
from txtlocal.slices.messaging.tests.support import (
    ACCOUNT,
    CAMPAIGN,
    DESTINATION,
    MAX_PRICE_USD,
    MODE,
    NOW,
    TWO_WAY_NUMBER,
    FakeMediaStorage,
    InMemoryMessagingRepo,
    OptOutSet,
    RecordingGateway,
    build_service,
    inbound,
    inbound_row_at,
    job,
    row_at,
)

TODAY = NOW.date()
LOG_FIELDS = frozenset(
    {
        "account_id",
        "campaign_id",
        "country",
        "encoding",
        "message_id",
        "mode",
        "parts",
        "price_micro",
        "product",
        "sender_id",
        "sender_kind",
        "user_id",
    }
)


class ThrottledOnMarkSent(InMemoryMessagingRepo):
    async def mark_sent(self, key: MessageKey, provider_message_id: str, sent_at: datetime) -> bool:
        del key, provider_message_id, sent_at
        raise Internal("ProvisionedThroughputExceededException")


def built() -> tuple[MessagingService, InMemoryMessagingRepo, RecordingGateway]:
    repo = InMemoryMessagingRepo()
    gateway = RecordingGateway(clock=lambda: NOW)
    return build_service(repo, gateway), repo, gateway


def event(event_type: str, key: str | None, message_id: str = "aws-1") -> ProviderEvent:
    context = {} if key is None else {"messageKey": key}
    return ProviderEvent(
        context=context, event_timestamp=NOW, event_type=event_type, message_id=message_id
    )


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("Hello", BodyQuote(chars=5, encoding=Encoding.GSM7, parts=1)),
        ("€" * 80, BodyQuote(chars=160, encoding=Encoding.GSM7, parts=1)),
        ("你" * 71, BodyQuote(chars=71, encoding=Encoding.UCS2, parts=2)),
        ("", BodyQuote(chars=0, encoding=Encoding.GSM7, parts=0)),
    ],
    ids=["plain-gsm", "extension-chars-count-twice", "autodetect-switches-to-ucs2", "empty"],
)
def test_quote_counts_the_body(body: str, expected: BodyQuote) -> None:
    service, _, _ = built()

    assert service.quote(body, MessagingSettings()) == expected


@pytest.mark.parametrize(
    ("body", "parts"),
    [("a" * 306, 2), ("a" * 307, 3)],
    ids=["at-the-account-limit", "one-part-over-the-account-limit"],
)
def test_quote_against_the_account_limit(body: str, parts: int) -> None:
    service, _, _ = built()
    settings = MessagingSettings(max_parts=2)

    if parts <= settings.max_parts:
        assert service.quote(body, settings).parts == parts
        return

    with pytest.raises(BadRequest) as caught:
        service.quote(body, settings)
    assert str(caught.value) == "Message needs 3 parts; your limit is 2"


@pytest.mark.parametrize(
    ("body", "accepted"),
    [("a" * 1224, True), ("a" * 1225, False)],
    ids=["eight-parts-is-the-product-ceiling", "nine-parts-is-refused-whatever-the-setting"],
)
def test_quote_never_exceeds_the_product_ceiling(body: str, accepted: bool) -> None:
    service, _, _ = built()
    settings = MessagingSettings(max_parts=20)

    if accepted:
        assert service.quote(body, settings).parts == 8
        return

    with pytest.raises(BadRequest) as caught:
        service.quote(body, settings)
    assert str(caught.value) == "Message needs 9 parts; your limit is 8"


def test_quote_in_gsm_only_mode_names_the_offending_character() -> None:
    service, _, _ = built()

    with pytest.raises(BadRequest) as caught:
        service.quote("Hello 你好", MessagingSettings(unicode_mode=UnicodeMode.GSM_ONLY))

    assert str(caught.value) == 'Character "你" is not available in GSM mode'


async def test_dispatch_accepts_and_marks_the_row_sent() -> None:
    service, repo, _ = built()

    dispatched = await service.dispatch(job(), NOW)

    row = repo.rows[message_key_for(ACCOUNT, dispatched.message_id)]
    assert dispatched.outcome is DispatchOutcome.ACCEPTED
    assert (row.status, row.provider_message_id, row.sent_at) == (
        MessageStatus.SENT,
        "provider-1",
        NOW,
    )


async def test_dispatch_sends_one_dispatch_shaped_from_the_job() -> None:
    service, repo, gateway = built()

    dispatched = await service.dispatch(job(), NOW)

    key = message_key_for(ACCOUNT, dispatched.message_id)
    assert gateway.dispatches == [
        Dispatch(
            body="Hello",
            destination=DESTINATION,
            max_price_usd=MAX_PRICE_USD,
            message_key=str(key),
            message_type=MessageType.PROMOTIONAL,
            origination="pool-1",
            ttl_seconds=3_600,
        )
    ]
    assert repo.rows[key].queued_at == NOW


async def test_dispatch_logs_message_accepted_with_ids_and_never_the_number(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service, _, _ = built()
    caplog.set_level(logging.INFO, logger="txtlocal")

    dispatched = await service.dispatch(job(), NOW)

    accepted = [r for r in caplog.records if r.getMessage() == MESSAGE_ACCEPTED]
    assert len(accepted) == 1
    fields: dict[str, object] = accepted[0].__dict__["fields"]
    assert set(fields) == LOG_FIELDS
    assert (fields["message_id"], fields["mode"], fields["campaign_id"]) == (
        dispatched.message_id,
        MODE,
        CAMPAIGN,
    )
    assert DESTINATION not in str(fields)
    assert "Hello" not in str(fields)


async def test_dispatch_of_the_same_job_twice_is_a_duplicate_and_calls_the_gateway_once() -> None:
    service, _, gateway = built()

    first = await service.dispatch(job(), NOW)
    second = await service.dispatch(job(), NOW + timedelta(seconds=5))

    assert second.outcome is DispatchOutcome.DUPLICATE
    assert second.message_id == first.message_id
    assert len(gateway.dispatches) == 1


@pytest.mark.parametrize(
    ("age", "outcome", "sends"),
    [
        (timedelta(seconds=60), DispatchOutcome.ACCEPTED, 1),
        (timedelta(seconds=59), DispatchOutcome.DUPLICATE, 0),
    ],
    ids=[
        "queued-sixty-seconds-ago-is-a-crash-and-resumes",
        "queued-fifty-nine-seconds-ago-is-in-flight",
    ],
)
async def test_dispatch_resumes_only_a_stale_queued_claim(
    age: timedelta, outcome: DispatchOutcome, sends: int
) -> None:
    service, repo, gateway = built()
    stale = row_at(NOW - age)
    assert await repo.claim(stale)

    dispatched = await service.dispatch(job(), NOW)

    assert (dispatched.outcome, dispatched.message_id) == (outcome, stale.message_id)
    assert len(gateway.dispatches) == sends


async def test_dispatch_refuses_an_opted_out_number_before_sending() -> None:
    repo, gateway = InMemoryMessagingRepo(), RecordingGateway(clock=lambda: NOW)
    service = build_service(repo, gateway, opt_outs=OptOutSet(frozenset({DESTINATION})))

    dispatched = await service.dispatch(job(), NOW)

    row = repo.rows[message_key_for(ACCOUNT, dispatched.message_id)]
    assert (dispatched.outcome, dispatched.failure_reason) == (
        DispatchOutcome.REFUSED,
        RefusalReason.OPTED_OUT,
    )
    assert (row.status, row.failure_reason) == (MessageStatus.FAILED, RefusalReason.OPTED_OUT)
    assert gateway.dispatches == []


async def test_dispatch_refuses_the_send_over_the_daily_cap() -> None:
    repo, gateway = InMemoryMessagingRepo(), RecordingGateway(clock=lambda: NOW)
    service = build_service(repo, gateway, daily_cap=2)

    outcomes = [
        (await service.dispatch(job(campaign_id=f"camp-{i}"), NOW)).outcome for i in range(3)
    ]

    assert outcomes == [
        DispatchOutcome.ACCEPTED,
        DispatchOutcome.ACCEPTED,
        DispatchOutcome.REFUSED,
    ]
    assert await service.sends_today(ACCOUNT, NOW) == 3


async def test_dispatch_settles_a_gateway_refusal_as_failed_with_the_reason() -> None:
    service, repo, gateway = built()
    gateway.failures.append(BadRequest("INVALID_PARAMETER"))

    dispatched = await service.dispatch(job(), NOW)

    row = repo.rows[message_key_for(ACCOUNT, dispatched.message_id)]
    assert (dispatched.outcome, dispatched.failure_reason) == (
        DispatchOutcome.REFUSED,
        "INVALID_PARAMETER",
    )
    assert (row.status, row.failure_reason) == (MessageStatus.FAILED, "INVALID_PARAMETER")


async def test_dispatch_settles_a_spend_quota_as_spend_limit() -> None:
    service, repo, gateway = built()
    gateway.failures.append(RateLimited("MONTHLY_SPEND_LIMIT_REACHED_FOR_TEXT"))

    dispatched = await service.dispatch(job(), NOW)

    assert dispatched.failure_reason == SPEND_LIMIT
    assert repo.rows[message_key_for(ACCOUNT, dispatched.message_id)].failure_reason == SPEND_LIMIT


async def test_dispatch_lets_an_upstream_failure_propagate_and_leaves_the_row_queued() -> None:
    service, repo, gateway = built()
    gateway.failures.append(Upstream("ThrottlingException"))

    with pytest.raises(Upstream):
        await service.dispatch(job(), NOW)

    assert [row.status for row in repo.rows.values()] == [MessageStatus.QUEUED]


@pytest.mark.parametrize(
    ("event_type", "expected"),
    [
        ("TEXT_QUEUED", MessageStatus.SENT),
        ("TEXT_PENDING", MessageStatus.SENT),
        ("TEXT_SENT", MessageStatus.SENT),
        ("TEXT_SUCCESSFUL", MessageStatus.DELIVERED),
        ("TEXT_DELIVERED", MessageStatus.DELIVERED),
        ("TEXT_INVALID", MessageStatus.FAILED),
        ("TEXT_INVALID_MESSAGE", MessageStatus.FAILED),
        ("TEXT_UNREACHABLE", MessageStatus.FAILED),
        ("TEXT_CARRIER_UNREACHABLE", MessageStatus.FAILED),
        ("TEXT_BLOCKED", MessageStatus.FAILED),
        ("TEXT_CARRIER_BLOCKED", MessageStatus.FAILED),
        ("TEXT_SPAM", MessageStatus.FAILED),
        ("TEXT_TTL_EXPIRED", MessageStatus.FAILED),
        ("TEXT_UNKNOWN", MessageStatus.FAILED),
        ("TEXT_PROTECT_BLOCKED", MessageStatus.FAILED),
        ("MEDIA_DELIVERED", MessageStatus.DELIVERED),
        ("MEDIA_FILE_SIZE_EXCEEDED", MessageStatus.FAILED),
        ("VOICE_COMPLETED", None),
        ("TEXT_SOMETHING_NEW", None),
        ("TEXT", None),
    ],
    ids=[
        "queued-is-sent",
        "pending-is-sent",
        "sent-is-sent",
        "successful-is-delivered",
        "delivered-is-delivered",
        "invalid-fails",
        "invalid-message-fails",
        "unreachable-fails",
        "carrier-unreachable-fails",
        "blocked-fails",
        "carrier-blocked-fails",
        "spam-fails",
        "ttl-expired-fails",
        "unknown-fails",
        "protect-blocked-fails",
        "media-maps-by-suffix",
        "media-file-size-fails",
        "voice-is-unmapped",
        "novel-name-is-unmapped",
        "no-suffix-is-unmapped",
    ],
)
def test_status_of_event(event_type: str, expected: MessageStatus | None) -> None:
    assert status_of_event(event_type) is expected


async def test_apply_event_delivers_a_sent_row() -> None:
    service, repo, _ = built()
    dispatched = await service.dispatch(job(), NOW)
    key = message_key_for(ACCOUNT, dispatched.message_id)
    later = NOW + timedelta(seconds=3)

    transition = await service.apply_event(event("TEXT_DELIVERED", str(key)), later)

    assert transition == Transition(
        account_id=ACCOUNT,
        campaign_id=CAMPAIGN,
        failure_reason=None,
        message_id=dispatched.message_id,
        status=MessageStatus.DELIVERED,
    )
    assert (repo.rows[key].status, repo.rows[key].delivered_at) == (
        MessageStatus.DELIVERED,
        later,
    )


async def test_apply_event_fails_a_row_with_the_event_name() -> None:
    service, repo, _ = built()
    dispatched = await service.dispatch(job(), NOW)
    key = message_key_for(ACCOUNT, dispatched.message_id)

    transition = await service.apply_event(event("TEXT_CARRIER_UNREACHABLE", str(key)), NOW)

    assert transition is not None
    assert (transition.status, transition.failure_reason) == (
        MessageStatus.FAILED,
        "TEXT_CARRIER_UNREACHABLE",
    )
    assert repo.rows[key].failure_reason == "TEXT_CARRIER_UNREACHABLE"


async def test_apply_event_that_overtakes_the_sent_write_completes_the_row() -> None:
    service, repo, _ = built()
    queued = row_at(NOW)
    repo.seed(queued)

    transition = await service.apply_event(event("TEXT_DELIVERED", str(queued.key)), NOW)

    row = repo.rows[queued.key]
    assert transition is not None
    assert (row.status, row.provider_message_id, row.sent_at) == (
        MessageStatus.DELIVERED,
        "aws-1",
        NOW,
    )


async def test_apply_event_late_sent_never_regresses_delivered() -> None:
    service, repo, _ = built()
    dispatched = await service.dispatch(job(), NOW)
    key = message_key_for(ACCOUNT, dispatched.message_id)
    await service.apply_event(event("TEXT_DELIVERED", str(key)), NOW)

    lost = await service.apply_event(event("TEXT_SENT", str(key)), NOW)

    assert lost is None
    assert repo.rows[key].status is MessageStatus.DELIVERED


async def test_apply_event_repeated_is_a_lost_condition() -> None:
    service, _, _ = built()
    dispatched = await service.dispatch(job(), NOW)
    key = str(message_key_for(ACCOUNT, dispatched.message_id))

    first = await service.apply_event(event("TEXT_DELIVERED", key), NOW)
    second = await service.apply_event(event("TEXT_DELIVERED", key), NOW)

    assert first is not None
    assert second is None


@pytest.mark.parametrize(
    ("event_type", "key"),
    [("VOICE_COMPLETED", "pk|sk"), ("TEXT_DELIVERED", None), ("TEXT_DELIVERED", "nonsense")],
    ids=["unmapped-type", "no-message-key", "malformed-message-key"],
)
async def test_apply_event_ignores_what_it_cannot_apply(event_type: str, key: str | None) -> None:
    service, _, _ = built()

    assert await service.apply_event(event(event_type, key), NOW) is None


async def test_record_inbound_creates_a_received_row_on_the_conversation() -> None:
    service, repo, _ = built()

    recorded = await service.record_inbound(ACCOUNT, inbound(), NOW)

    assert recorded is True
    row = next(iter(repo.rows.values()))
    assert (row.direction, row.status, row.from_, row.to, row.body, row.campaign_id) == (
        Direction.IN,
        MessageStatus.RECEIVED,
        DESTINATION,
        TWO_WAY_NUMBER,
        "Hello",
        "",
    )
    assert row.queued_at == NOW


async def test_record_inbound_of_a_redelivered_notification_writes_once() -> None:
    service, repo, _ = built()

    first = await service.record_inbound(ACCOUNT, inbound(), NOW)
    second = await service.record_inbound(ACCOUNT, inbound(), NOW + timedelta(minutes=5))

    assert (first, second) == (True, False)
    assert len(repo.rows) == 1


async def test_record_inbound_of_a_different_notification_writes_a_second_row() -> None:
    service, repo, _ = built()

    await service.record_inbound(ACCOUNT, inbound(), NOW)
    other = await service.record_inbound(
        ACCOUNT, inbound(inbound_message_id="inbound-2"), NOW + timedelta(minutes=5)
    )

    assert other is True
    assert len(repo.rows) == 2


async def test_find_by_provider_id_resolves_the_sent_row() -> None:
    service, _, _ = built()
    dispatched = await service.dispatch(job(), NOW)

    ref = await service.find_by_provider_id("provider-1")

    assert ref == MessageRef(
        account_id=ACCOUNT,
        campaign_id=CAMPAIGN,
        message_id=dispatched.message_id,
        peer=DESTINATION,
        sender_id="sender-1",
    )


async def test_find_by_provider_id_of_an_unknown_id_is_none() -> None:
    service, _, _ = built()

    assert await service.find_by_provider_id("nonsense") is None


async def test_history_defaults_to_the_last_seven_days_newest_first() -> None:
    service, repo, _ = built()
    today, edge, outside = (
        row_at(NOW, 1),
        row_at(NOW - timedelta(days=7), 2),
        row_at(NOW - timedelta(days=8), 3),
    )
    repo.seed(edge, outside, today)

    page = await service.history(ACCOUNT, HistoryQuery(), NOW)

    assert [row.message_id for row in page.items] == [today.message_id, edge.message_id]
    assert page.cursor is None


@pytest.mark.parametrize(
    ("days_back", "accepted"),
    [(RETENTION_DAYS, True), (RETENTION_DAYS + 1, False)],
    ids=["one-hundred-and-twenty-days-back-is-served", "one-day-further-is-refused"],
)
async def test_history_range_ceiling(days_back: int, accepted: bool) -> None:
    service, _, _ = built()
    query = HistoryQuery(since=TODAY - timedelta(days=days_back))

    if accepted:
        assert (await service.history(ACCOUNT, query, NOW)).items == []
        return

    with pytest.raises(BadRequest) as caught:
        await service.history(ACCOUNT, query, NOW)
    assert str(caught.value) == HISTORY_TOO_FAR_BACK


async def test_history_refuses_an_inverted_range() -> None:
    service, _, _ = built()

    with pytest.raises(BadRequest) as caught:
        await service.history(
            ACCOUNT, HistoryQuery(since=TODAY, until=TODAY - timedelta(days=1)), NOW
        )

    assert str(caught.value) == RANGE_INVERTED


async def test_history_clamps_a_future_end_date_to_today() -> None:
    service, repo, _ = built()
    repo.seed(row_at(NOW))

    page = await service.history(ACCOUNT, HistoryQuery(until=TODAY + timedelta(days=30)), NOW)

    assert len(page.items) == 1


async def test_history_pages_across_month_partitions_with_a_cursor() -> None:
    service, repo, _ = built()
    september = [row_at(NOW - timedelta(minutes=i), i) for i in range(25)]
    august = [row_at(NOW - timedelta(days=30, minutes=i), 100 + i) for i in range(20)]
    repo.seed(*september, *august)
    query = HistoryQuery(since=date(2026, 8, 1))

    first = await service.history(ACCOUNT, query, NOW)
    second = await service.history(ACCOUNT, query.model_copy(update={"cursor": first.cursor}), NOW)
    third = await service.history(ACCOUNT, query.model_copy(update={"cursor": second.cursor}), NOW)

    seen = [row.message_id for page in (first, second, third) for row in page.items]
    assert [len(first.items), len(second.items), len(third.items)] == [PAGE_SIZE, PAGE_SIZE, 5]
    assert seen == [row.message_id for row in september + august]
    assert third.cursor is None


async def test_history_searches_an_exact_normalised_number_on_the_chosen_field() -> None:
    service, repo, _ = built()
    hit = row_at(NOW, 1)
    other = row_at(NOW - timedelta(minutes=1), 2, to=E164("+447400123106"))
    repo.seed(hit, other)

    by_to = await service.history(ACCOUNT, HistoryQuery(q="07400 123105"), NOW)
    by_from = await service.history(
        ACCOUNT, HistoryQuery(field=SearchField.FROM, q="+447400123105"), NOW
    )

    assert [row.message_id for row in by_to.items] == [hit.message_id]
    assert by_from.items == []


async def test_history_refuses_an_unparseable_search_number() -> None:
    service, _, _ = built()

    with pytest.raises(BadRequest) as caught:
        await service.history(ACCOUNT, HistoryQuery(q="not a number"), NOW)

    assert str(caught.value) == INVALID_NUMBER_MESSAGE


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (Product.SMS, ["sms"]),
        (Product.MMS, ["mms", "link"]),
        (Product.MMS_AS_LINK, ["link"]),
        (None, ["sms", "mms", "link"]),
    ],
    ids=["sms-only", "mms-includes-rows-delivered-as-a-link", "link-only", "no-filter"],
)
async def test_history_filters_by_kind(kind: Product | None, expected: list[str]) -> None:
    service, repo, _ = built()
    rows = {
        "sms": row_at(NOW, 1, product=Product.SMS),
        "mms": row_at(NOW - timedelta(minutes=1), 2, product=Product.MMS),
        "link": row_at(NOW - timedelta(minutes=2), 3, product=Product.MMS_AS_LINK),
    }
    repo.seed(*rows.values())

    page = await service.history(ACCOUNT, HistoryQuery(kind=kind), NOW)

    assert [row.message_id for row in page.items] == [rows[name].message_id for name in expected]


async def test_history_refuses_a_malformed_cursor() -> None:
    service, _, _ = built()

    with pytest.raises(BadRequest) as caught:
        await service.history(ACCOUNT, HistoryQuery(cursor="not-base64!"), NOW)

    assert str(caught.value) == INVALID_CURSOR


async def test_detail_returns_the_row() -> None:
    service, repo, _ = built()
    row = row_at(NOW)
    repo.seed(row)

    assert await service.detail(ACCOUNT, row.message_id) == row


@pytest.mark.parametrize(
    "message_id",
    [str(uuid7_at(NOW, Random(99))), "not-a-uuid"],
    ids=["unknown-id", "malformed-id"],
)
async def test_detail_not_found(message_id: str) -> None:
    service, _, _ = built()

    with pytest.raises(NotFound) as caught:
        await service.detail(ACCOUNT, message_id)

    assert str(caught.value) == MESSAGE_NOT_FOUND


async def test_conversation_messages_returns_both_directions_newest_first() -> None:
    service, repo, _ = built()
    reply = row_at(NOW - timedelta(minutes=5), 1)
    received = inbound_row_at(NOW, 2)
    unrelated = row_at(NOW - timedelta(minutes=1), 3, to=E164("+447400123106"))
    repo.seed(reply, received, unrelated)

    page = await service.conversation_messages(ACCOUNT, DESTINATION, None)

    assert [row.message_id for row in page.items] == [received.message_id, reply.message_id]
    assert page.next_cursor is None


async def test_conversation_messages_pages_newest_first_with_a_cursor() -> None:
    service, repo, _ = built()
    thread = [inbound_row_at(NOW - timedelta(minutes=i), i) for i in range(PAGE_SIZE + 5)]
    repo.seed(*thread)

    first = await service.conversation_messages(ACCOUNT, DESTINATION, None)
    second = await service.conversation_messages(ACCOUNT, DESTINATION, first.next_cursor)

    assert [len(first.items), len(second.items)] == [PAGE_SIZE, 5]
    assert [row.message_id for row in first.items + second.items] == [
        row.message_id for row in thread
    ]
    assert second.next_cursor is None


async def exported(service: MessagingService) -> list[str]:
    return "".join([chunk async for chunk in service.export(ACCOUNT, HistoryQuery(), NOW)]).split(
        "\n"
    )


async def test_export_writes_the_screen_columns() -> None:
    service, repo, _ = built()
    repo.seed(row_at(NOW))

    lines = await exported(service)

    assert lines[0] == "username,date,from,to,status,body"
    assert lines[1] == f"demo,{NOW.isoformat()},SHARED,+447400123105,QUEUED,Hello"
    assert lines[2:] == [""]


@pytest.mark.parametrize(
    ("rows", "truncated"),
    [(EXPORT_MAX_ROWS, False), (EXPORT_MAX_ROWS + 1, True)],
    ids=["ten-thousand-rows-fit", "row-ten-thousand-and-one-is-dropped-and-marked"],
)
async def test_export_ceiling(rows: int, truncated: bool) -> None:
    service, repo, _ = built()
    repo.seed(*(row_at(NOW - timedelta(milliseconds=i), i) for i in range(rows)))

    lines = await exported(service)

    data_lines = [line for line in lines[1:] if line and not line.startswith("#")]
    assert len(data_lines) == EXPORT_MAX_ROWS
    assert (lines[-2] == EXPORT_TRUNCATED) is truncated


async def test_templates_are_created_listed_edited_and_deleted() -> None:
    service, _, _ = built()

    created = await service.create_template(
        ACCOUNT, TemplateRequest(body="Hi", name="Greeting"), NOW
    )
    edited = await service.update_template(
        ACCOUNT, created.template_id, TemplateRequest(body="Hello", name="Greeting v2")
    )
    listed = await service.list_templates(ACCOUNT)
    await service.delete_template(ACCOUNT, created.template_id)

    assert (edited.body, edited.name, edited.created_at) == ("Hello", "Greeting v2", NOW)
    assert listed == [edited]
    assert await service.list_templates(ACCOUNT) == []


async def test_update_of_an_unknown_template_is_not_found() -> None:
    service, _, _ = built()

    with pytest.raises(NotFound) as caught:
        await service.update_template(ACCOUNT, "missing", TemplateRequest(body="x", name="y"))

    assert str(caught.value) == TEMPLATE_NOT_FOUND


async def test_delete_of_an_unknown_template_is_not_found() -> None:
    service, _, _ = built()

    with pytest.raises(NotFound) as caught:
        await service.delete_template(ACCOUNT, "missing")

    assert str(caught.value) == TEMPLATE_NOT_FOUND


def built_with_media() -> tuple[MessagingService, RecordingGateway, FakeMediaStorage]:
    gateway = RecordingGateway(clock=lambda: NOW)
    media = FakeMediaStorage()
    service = build_service(InMemoryMessagingRepo(), gateway, media=media)
    return service, gateway, media


@pytest.mark.parametrize(
    ("body", "accepted"),
    [("a" * MMS_MAX_CHARS, True), ("a" * (MMS_MAX_CHARS + 1), False)],
    ids=["fifteen-hundred-characters-is-the-mms-ceiling", "fifteen-hundred-and-one-is-refused"],
)
def test_quote_mms_never_exceeds_its_own_ceiling(body: str, accepted: bool) -> None:
    service, _, _ = built()

    if accepted:
        assert service.quote_mms(body) == BodyQuote(
            chars=MMS_MAX_CHARS, encoding=Encoding.GSM7, parts=1
        )
        return

    with pytest.raises(BadRequest) as caught:
        service.quote_mms(body)
    assert str(caught.value) == MMS_TOO_LONG_MESSAGE.format(limit=MMS_MAX_CHARS)


async def test_dispatch_sends_media_for_an_mms_job() -> None:
    repo = InMemoryMessagingRepo()
    media = FakeMediaStorage()
    gateway = RecordingGateway(clock=lambda: NOW)
    service = build_service(repo, gateway, media=media)

    dispatched = await service.dispatch(
        job(media_key="media-1", product=Product.MMS, subject="Look"), NOW
    )

    assert dispatched.outcome is DispatchOutcome.ACCEPTED
    key = message_key_for(ACCOUNT, dispatched.message_id)
    assert gateway.dispatches == [
        MediaDispatch(
            body="Hello",
            destination=DESTINATION,
            max_price_usd=MAX_PRICE_USD,
            media_urls=(media.public_url("media-1"),),
            message_key=str(key),
            message_type=MessageType.PROMOTIONAL,
            origination="pool-1",
            subject="Look",
            ttl_seconds=3_600,
        )
    ]
    row = repo.rows[key]
    assert (row.kind, row.media_key, row.subject) == (Product.MMS, "media-1", "Look")


async def test_dispatch_of_an_mms_job_without_a_media_key_is_an_internal_error() -> None:
    service, _, _ = built()

    with pytest.raises(Internal) as caught:
        await service.dispatch(job(product=Product.MMS, media_key=None), NOW)
    assert str(caught.value) == MMS_JOB_MISSING_MEDIA


async def test_dispatch_of_an_mms_as_link_job_sends_plain_text() -> None:
    service, _, gateway = built()

    dispatched = await service.dispatch(
        job(body="Hi\n\nhttps://x/y.png", product=Product.MMS_AS_LINK), NOW
    )

    assert dispatched.outcome is DispatchOutcome.ACCEPTED
    assert gateway.dispatches == [
        Dispatch(
            body="Hi\n\nhttps://x/y.png",
            destination=DESTINATION,
            max_price_usd=MAX_PRICE_USD,
            message_key=str(message_key_for(ACCOUNT, dispatched.message_id)),
            message_type=MessageType.PROMOTIONAL,
            origination="pool-1",
            ttl_seconds=3_600,
        )
    ]


async def test_create_media_upload_accepts_a_known_content_type() -> None:
    service, _, media = built_with_media()

    upload = await service.create_media_upload("image/png")

    assert (upload.key, upload.upload_url) == ("media-1", media.public_url("media-1"))
    assert media.minted == ["image/png"]


async def test_create_media_upload_refuses_an_unknown_content_type() -> None:
    service, _, _ = built_with_media()

    with pytest.raises(BadRequest) as caught:
        await service.create_media_upload("application/pdf")
    assert str(caught.value) == MEDIA_TYPE_MESSAGE


async def test_store_media_writes_through_to_storage() -> None:
    service, _, media = built_with_media()

    await service.store_media("a.png", "image/png", b"pixels")

    assert media.files["a.png"].body == b"pixels"


async def test_store_media_refuses_a_body_over_the_size_ceiling() -> None:
    service, _, _ = built_with_media()

    with pytest.raises(BadRequest) as caught:
        await service.store_media("a.png", "image/png", b"x" * (MAX_MEDIA_BYTES + 1))
    assert str(caught.value) == MEDIA_TOO_LARGE_MESSAGE


async def test_store_media_refuses_an_unknown_content_type() -> None:
    service, _, _ = built_with_media()

    with pytest.raises(BadRequest) as caught:
        await service.store_media("a.png", "application/pdf", b"x")
    assert str(caught.value) == MEDIA_TYPE_MESSAGE


async def test_read_media_answers_a_stored_file() -> None:
    service, _, media = built_with_media()
    await media.store("a.png", "image/png", b"pixels")

    file = await service.read_media("a.png")

    assert (file.body, file.content_type) == (b"pixels", "image/png")


async def test_read_media_of_an_unknown_key_is_not_found() -> None:
    service, _, _ = built_with_media()

    with pytest.raises(NotFound) as caught:
        await service.read_media("missing.png")
    assert str(caught.value) == MEDIA_NOT_FOUND


async def test_dispatch_never_resumes_a_claim_the_provider_may_have_seen() -> None:
    service, repo, gateway = built()
    stale = row_at(NOW - STALE_CLAIM)
    assert await repo.claim(stale)
    assert await repo.claim_attempt(stale.key, NOW - STALE_CLAIM)

    dispatched = await service.dispatch(job(), NOW)

    assert (dispatched.outcome, len(gateway.dispatches)) == (DispatchOutcome.DUPLICATE, 0)


async def test_a_redelivered_job_whose_mark_sent_failed_is_not_sent_again() -> None:
    repo = ThrottledOnMarkSent()
    gateway = RecordingGateway(clock=lambda: NOW)
    service = build_service(repo, gateway)
    with pytest.raises(Internal):
        await service.dispatch(job(), NOW)

    dispatched = await service.dispatch(job(), NOW + STALE_CLAIM)

    assert (dispatched.outcome, len(gateway.dispatches)) == (DispatchOutcome.DUPLICATE, 1)


async def test_a_redelivered_job_whose_mark_sent_failed_is_counted_once() -> None:
    repo = ThrottledOnMarkSent()
    service = build_service(repo, RecordingGateway(clock=lambda: NOW))
    with pytest.raises(Internal):
        await service.dispatch(job(), NOW)

    await service.dispatch(job(), NOW + STALE_CLAIM)

    assert await repo.sends_on(ACCOUNT, TODAY) == 1

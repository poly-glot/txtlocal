from collections.abc import Sequence
from datetime import datetime, timedelta

import pytest

from txtlocal.shared.bus import Queue
from txtlocal.shared.errors import (
    AppError,
    BadRequest,
    Conflict,
    Forbidden,
    Internal,
    NotFound,
    PaymentRequired,
    RateLimited,
)
from txtlocal.shared.money import Micro
from txtlocal.shared.phone import E164, INVALID_NUMBER_MESSAGE
from txtlocal.slices.campaigns.model import (
    Campaign,
    CampaignCounter,
    CampaignCounts,
    CampaignDraft,
    CampaignKind,
    CampaignStatus,
    OptOutMode,
    QuickSendResult,
    Refusal,
)
from txtlocal.slices.campaigns.service import (
    ALPHA_NEEDS_LINK,
    CAMPAIGN_NOT_FOUND,
    CAMPAIGN_SENDING,
    COPY_SUFFIX,
    DRAFT_ONLY,
    DUE_LIMIT,
    MAX_RECIPIENTS,
    NEEDS_BODY,
    NEEDS_LIST,
    NEEDS_MEDIA,
    NO_RECIPIENTS,
    NOT_SCHEDULED,
    REPLY_STOP_FOOTER,
    SCHEDULE_TOO_LATE,
    SCHEDULE_TOO_SOON,
    STUCK_AFTER,
    TOO_MANY_RECIPIENTS,
    UNKNOWN_LINK,
    UNSUBSCRIBE_FOOTER,
    billed_parts,
    counter_of,
    default_footer,
    parts_of,
    per_message_quote,
    quick_name,
    rate_product_of,
    refusal_error,
    render,
    scheduled_time,
    unique_recipients,
    unsubscribe_token,
    unsubscribed_of,
    with_footer,
    with_media_link,
)
from txtlocal.slices.campaigns.tests.fakes import (
    ACCOUNT_ID,
    BODY,
    FR_ONE,
    GB_ONE,
    GB_RATE,
    GB_TWO,
    LIST_ID,
    LIST_NOT_FOUND,
    MEDIA_KEY,
    MEDIA_URL,
    NOW,
    PRINCIPAL,
    SECRET,
    SHARED_POOL,
    SHARED_VALUE,
    SITE,
    US_ONE,
    FakeRecipient,
    World,
    contact,
    contacts_of,
    draft_campaign,
    list_campaign,
    world,
)
from txtlocal.slices.messaging.model import (
    CAMPAIGN_TTL_SECONDS,
    BodyQuote,
    DispatchOutcome,
    MessageType,
    Product,
    QuickSendRequest,
    RefusalReason,
    SendJob,
)
from txtlocal.slices.messaging.policy import (
    COUNTRY_NOT_ENABLED_MESSAGE,
    DAILY_CAP_MESSAGE,
    OPTED_OUT_MESSAGE,
    TRIAL_ENDED_MESSAGE,
)
from txtlocal.slices.messaging.segments import Encoding, encoding_of, segments_of

GB_ONLY = frozenset({"GB"})
LONG_NAME = "A" * 200
ONE_PART_BODY = "A" * 155
TWO_GB = (GB_ONE, GB_TWO)


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (RefusalReason.COUNTRY_NOT_ENABLED, BadRequest),
        (RefusalReason.DAILY_CAP, RateLimited),
        (RefusalReason.INSUFFICIENT_BALANCE, PaymentRequired),
        (RefusalReason.NOT_VERIFIED, BadRequest),
        (RefusalReason.OPTED_OUT, BadRequest),
        (RefusalReason.SENDER_NOT_READY, BadRequest),
        (RefusalReason.TRIAL_ENDED, Forbidden),
    ],
    ids=lambda value: value if isinstance(value, str) else value.__name__,
)
def test_a_refusal_carries_its_own_status(reason: RefusalReason, expected: type[AppError]) -> None:
    error = refusal_error(Refusal(message="refused", reason=reason, to="+447400123105"))

    assert isinstance(error, expected)
    assert str(error) == "refused"


def quick(to: Sequence[str], send_at: datetime | None = None) -> QuickSendRequest:
    return QuickSendRequest(body=BODY, send_at=send_at, to=list(to))


def listed(to: Sequence[str]) -> QuickSendRequest:
    return QuickSendRequest(body=BODY, list_ids=[LIST_ID], to=list(to))


def personal(to: Sequence[str], send_at: datetime | None = None) -> QuickSendRequest:
    return QuickSendRequest(
        body="Hi {first_name}", list_ids=[LIST_ID], send_at=send_at, to=list(to)
    )


def gb_numbers(count: int) -> list[str]:
    return [f"+447400{index:06d}" for index in range(count)]


def stored(w: World, campaign_id: str) -> Campaign:
    return w.repo.rows[(ACCOUNT_ID, campaign_id)]


async def sent(w: World, to: Sequence[str] = TWO_GB) -> QuickSendResult:
    return await w.service.send_quick(PRINCIPAL, quick(to), NOW)


async def saved(w: World, campaign: Campaign) -> Campaign:
    await w.repo.put_draft(ACCOUNT_ID, campaign)
    return campaign


async def scheduled(w: World, campaign: Campaign, send_at: datetime | None = None) -> Campaign:
    await saved(w, campaign)
    return await w.service.schedule(PRINCIPAL, campaign.campaign_id, send_at, NOW)


async def fanned_out(w: World, campaign: Campaign) -> Campaign:
    (ref,) = await w.service.due(NOW, DUE_LIMIT)
    await w.service.claim_and_fan_out(ref, NOW)
    return stored(w, campaign.campaign_id)


def jobs_of(w: World) -> list[SendJob]:
    return [
        SendJob.model_validate_json(message.body) for _, batch in w.bus.sent for message in batch
    ]


@pytest.mark.parametrize(
    ("listed", "typed", "expected"),
    [
        ((), ["07400 123105", "+447400123105"], [GB_ONE]),
        ((), [GB_TWO, GB_ONE], [GB_TWO, GB_ONE]),
        ((contact(GB_ONE, "Ada"),), [GB_ONE], [GB_ONE]),
    ],
    ids=["national-and-e164-collapse", "order-kept", "a-list-member-typed-again-is-one"],
)
def test_unique_recipients(
    listed: tuple[FakeRecipient, ...], typed: list[str], expected: list[E164]
) -> None:
    assert [one.mobile for one in unique_recipients(listed, typed, "GB")] == expected


def test_unique_recipients_keeps_the_contacts_fields_over_a_typed_number() -> None:
    merged = unique_recipients([contact(GB_ONE, "Ada")], [GB_ONE], "GB")
    assert [one.recipient.fields.get("first_name") for one in merged] == ["Ada"]


@pytest.mark.parametrize(
    ("cost_micro", "recipients", "expected"),
    [(85_400, 2, 42_700), (100_001, 2, 50_001), (42_700, 1, 42_700)],
    ids=["even-split", "rounds-up", "single"],
)
def test_per_message_quote(cost_micro: int, recipients: int, expected: int) -> None:
    assert per_message_quote(Micro(cost_micro), recipients) == expected


def test_quick_name_carries_channel_and_time() -> None:
    assert quick_name(Product.SMS, NOW) == "Quick SMS 19 Sep 2026 12:00"


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (DispatchOutcome.ACCEPTED, CampaignCounter.SENT),
        (DispatchOutcome.REFUSED, CampaignCounter.REFUSED),
        (DispatchOutcome.DUPLICATE, None),
    ],
    ids=["accepted-counts-sent", "refused-counts-refused", "duplicate-counts-nothing"],
)
def test_counter_of(outcome: DispatchOutcome, expected: CampaignCounter | None) -> None:
    assert counter_of(outcome) is expected


@pytest.mark.parametrize(
    ("template", "fields", "expected"),
    [
        ("Hi {first_name}", {"first_name": "Ada"}, "Hi Ada"),
        ("Hi {first_name}", {}, "Hi "),
        ("Hi {nickname}", {"first_name": "Ada"}, "Hi {nickname}"),
        ("Save {50}% today", {}, "Save {50}% today"),
    ],
    ids=[
        "field-resolved",
        "absent-field-empty",
        "unknown-placeholder-left-alone",
        "braces-left-alone",
    ],
)
def test_render(template: str, fields: dict[str, str], expected: str) -> None:
    assert render(template, fields) == expected


@pytest.mark.parametrize(
    ("body", "footer", "expected"),
    [("Hello", "Reply STOP", "Hello\nReply STOP"), ("Hello", "", "Hello")],
    ids=["line-break-before-the-footer", "no-footer-no-break"],
)
def test_with_footer(body: str, footer: str, expected: str) -> None:
    assert with_footer(body, footer) == expected


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (OptOutMode.REPLY_STOP, REPLY_STOP_FOOTER),
        (OptOutMode.UNSUBSCRIBE_LINK, UNSUBSCRIBE_FOOTER),
    ],
    ids=["reply-stop", "unsubscribe-link"],
)
def test_default_footer(mode: OptOutMode, expected: str) -> None:
    assert default_footer(mode) == expected


def test_unsubscribe_token_round_trips_the_account_and_number() -> None:
    token = unsubscribe_token(SECRET, ACCOUNT_ID, GB_ONE)
    assert unsubscribed_of(SECRET, token) == (ACCOUNT_ID, GB_ONE)


@pytest.mark.parametrize(
    "token",
    ["", "nonsense", "AAAA.bm90LWEtcGF5bG9hZA"],
    ids=["empty", "unsigned", "wrong-signature"],
)
def test_unsubscribed_of_refuses_a_bad_token(token: str) -> None:
    assert unsubscribed_of(SECRET, token) is None


def test_unsubscribe_token_is_account_specific() -> None:
    token = unsubscribe_token(SECRET, "other-account", GB_ONE)
    assert unsubscribed_of(SECRET, token) == ("other-account", GB_ONE)


@pytest.mark.parametrize(
    "send_at",
    [NOW + timedelta(minutes=5), NOW + timedelta(days=365)],
    ids=["five-minutes-ahead", "twelve-months-ahead"],
)
def test_scheduled_time_accepts_the_window(send_at: datetime) -> None:
    assert scheduled_time(send_at, NOW) == send_at


def test_scheduled_time_reads_none_as_now() -> None:
    assert scheduled_time(None, NOW) == NOW


def test_scheduled_time_refuses_four_minutes_fifty_nine_seconds_ahead() -> None:
    with pytest.raises(BadRequest) as caught:
        scheduled_time(NOW + timedelta(minutes=4, seconds=59), NOW)
    assert str(caught.value) == SCHEDULE_TOO_SOON


def test_scheduled_time_refuses_a_day_past_twelve_months() -> None:
    with pytest.raises(BadRequest) as caught:
        scheduled_time(NOW + timedelta(days=366), NOW)
    assert str(caught.value) == SCHEDULE_TOO_LATE


async def test_quote_prices_two_gb_recipients_at_one_part() -> None:
    quote = await world().service.quote_quick(PRINCIPAL, quick(TWO_GB), NOW)
    assert (quote.cost_micro, quote.parts, quote.recipients, quote.refused) == (85_400, 1, 2, [])


async def test_quote_quick_shortens_urls_when_the_toggle_is_on() -> None:
    w = world()
    request = QuickSendRequest(body=BODY, shorten_urls=True, to=TWO_GB)
    await w.service.quote_quick(PRINCIPAL, request, NOW)
    assert w.links.calls == [(BODY, PRINCIPAL.account_id, "")]


async def test_quote_quick_leaves_shorten_urls_off_alone() -> None:
    w = world()
    await w.service.quote_quick(PRINCIPAL, quick(TWO_GB), NOW)
    assert w.links.calls == []


async def test_quote_prices_each_recipient_at_its_country_rate() -> None:
    quote = await world().service.quote_quick(PRINCIPAL, quick([GB_ONE, US_ONE]), NOW)
    assert quote.cost_micro == 50_700


async def test_quote_collapses_duplicate_numbers() -> None:
    quote = await world().service.quote_quick(PRINCIPAL, quick(["07400 123105", GB_ONE]), NOW)
    assert quote.recipients == 1


async def test_quote_accepts_a_thousand_recipients() -> None:
    quote = await world().service.quote_quick(PRINCIPAL, quick(gb_numbers(MAX_RECIPIENTS)), NOW)
    assert quote.recipients == MAX_RECIPIENTS


async def test_quote_refuses_a_thousand_and_one_recipients() -> None:
    with pytest.raises(BadRequest) as caught:
        await world().service.quote_quick(PRINCIPAL, quick(gb_numbers(MAX_RECIPIENTS + 1)), NOW)
    assert str(caught.value) == TOO_MANY_RECIPIENTS


async def test_quote_refuses_an_invalid_number_with_the_phone_message() -> None:
    with pytest.raises(BadRequest) as caught:
        await world().service.quote_quick(PRINCIPAL, quick([GB_ONE, "07700 900105"]), NOW)
    assert str(caught.value) == INVALID_NUMBER_MESSAGE


async def test_quote_refuses_an_empty_recipient_list() -> None:
    with pytest.raises(BadRequest) as caught:
        await world().service.quote_quick(PRINCIPAL, quick([]), NOW)
    assert str(caught.value) == NO_RECIPIENTS


async def test_quote_lists_refusals_with_reason_and_number() -> None:
    w = world(allowed=GB_ONLY)
    quote = await w.service.quote_quick(PRINCIPAL, quick([GB_ONE, FR_ONE]), NOW)
    assert quote.refused == [
        Refusal(
            message=COUNTRY_NOT_ENABLED_MESSAGE.format(country="FR"),
            reason=RefusalReason.COUNTRY_NOT_ENABLED,
            to=FR_ONE,
        )
    ]


async def test_quote_prices_only_accepted_recipients() -> None:
    w = world(allowed=GB_ONLY)
    quote = await w.service.quote_quick(PRINCIPAL, quick([GB_ONE, FR_ONE]), NOW)
    assert (quote.cost_micro, quote.recipients) == (GB_RATE, 1)


@pytest.mark.parametrize(
    "trial_ends_at",
    [NOW - timedelta(seconds=1), None],
    ids=["trial-expired", "no-trial-on-the-row"],
)
async def test_quote_refuses_every_recipient_after_the_trial(
    trial_ends_at: datetime | None,
) -> None:
    w = world(trial_ends_at=trial_ends_at)
    quote = await w.service.quote_quick(PRINCIPAL, quick(TWO_GB), NOW)
    assert [r.message for r in quote.refused] == [TRIAL_ENDED_MESSAGE, TRIAL_ENDED_MESSAGE]


@pytest.mark.parametrize(
    ("sent_today", "refused"),
    [(499, 0), (500, 2)],
    ids=["the-500th-send-fits", "the-501st-is-refused"],
)
async def test_quote_runs_the_daily_cap_against_todays_sends(sent_today: int, refused: int) -> None:
    w = world(sent_today=sent_today)
    quote = await w.service.quote_quick(PRINCIPAL, quick(TWO_GB), NOW)
    assert len(quote.refused) == refused


async def test_quote_refuses_at_the_daily_cap_with_the_policy_message() -> None:
    w = world(sent_today=500)
    quote = await w.service.quote_quick(PRINCIPAL, quick([GB_ONE]), NOW)
    assert [r.message for r in quote.refused] == [DAILY_CAP_MESSAGE]


async def test_quote_resolves_the_sender_once_per_country() -> None:
    w = world()
    await w.service.quote_quick(PRINCIPAL, quick([GB_ONE, US_ONE, GB_TWO]), NOW)
    assert sorted(w.senders.resolved) == [(ACCOUNT_ID, None, "GB"), (ACCOUNT_ID, None, "US")]


async def test_quote_reads_the_balance_once() -> None:
    w = world()
    await w.service.quote_quick(PRINCIPAL, quick([GB_ONE, US_ONE, GB_TWO]), NOW)
    assert w.billing.balance_reads == [(ACCOUNT_ID, NOW)]


async def test_send_refuses_with_the_first_refusal_when_nobody_is_left() -> None:
    with pytest.raises(BadRequest) as caught:
        await sent(world(allowed=frozenset()), [GB_ONE, US_ONE])
    assert str(caught.value) == COUNTRY_NOT_ENABLED_MESSAGE.format(country="GB")


async def test_send_reserves_the_total_against_the_campaign_id() -> None:
    w = world()
    result = await sent(w)
    assert w.billing.reserved == [(ACCOUNT_ID, Micro(85_400), result.campaign_id, NOW)]


async def test_send_leaves_the_campaign_draft_when_the_reserve_is_refused() -> None:
    w = world(refusal=PaymentRequired("Your balance is £0.00; this send costs £0.09"))
    with pytest.raises(PaymentRequired):
        await sent(w)
    assert [c.status for c in w.repo.rows.values()] == [CampaignStatus.DRAFT]


async def test_send_enqueues_nothing_when_the_reserve_is_refused() -> None:
    w = world(refusal=PaymentRequired("Your balance is £0.00; this send costs £0.09"))
    with pytest.raises(PaymentRequired):
        await sent(w)
    assert w.bus.sent == []


async def test_send_flips_the_campaign_to_sending_with_the_confirmation_counts() -> None:
    w = world(allowed=GB_ONLY)
    result = await sent(w, [GB_ONE, FR_ONE, GB_TWO])
    campaign = stored(w, result.campaign_id)
    assert (campaign.status, campaign.counts) == (
        CampaignStatus.SENDING,
        CampaignCounts(recipients=2),
    )


async def test_send_answers_the_confirmation_numbers() -> None:
    w = world(allowed=GB_ONLY)
    result = await sent(w, [GB_ONE, FR_ONE, GB_TWO])
    assert (result.cost_micro, result.recipients, [r.to for r in result.refused]) == (
        85_400,
        2,
        [FR_ONE],
    )


async def test_send_enqueues_jobs_in_batches_of_ten() -> None:
    w = world()
    await sent(w, gb_numbers(25))
    assert [(queue, len(batch)) for queue, batch in w.bus.sent] == [
        (Queue.SEND_JOBS, 10),
        (Queue.SEND_JOBS, 10),
        (Queue.SEND_JOBS, 5),
    ]


async def test_send_job_carries_the_wire_shape() -> None:
    w = world()
    result = await sent(w, [GB_ONE])
    assert SendJob.model_validate_json(w.bus.sent[0][1][0].body) == SendJob(
        account_id=ACCOUNT_ID,
        body=BODY,
        campaign_id=result.campaign_id,
        country="GB",
        encoding=Encoding.GSM7,
        message_type=MessageType.PROMOTIONAL,
        origination=SHARED_POOL,
        parts=1,
        price_micro=GB_RATE,
        product=Product.SMS,
        sender_id="smart-GB",
        sender_kind="SHARED",
        sender_value=SHARED_VALUE,
        to=GB_ONE,
        user_id=PRINCIPAL.user_id,
        username=PRINCIPAL.username,
    )


async def test_a_later_quick_send_is_scheduled_rather_than_enqueued() -> None:
    w = world()
    result = await w.service.send_quick(
        PRINCIPAL, quick(TWO_GB, send_at=NOW + timedelta(hours=2)), NOW
    )
    campaign = stored(w, result.campaign_id)
    assert (campaign.kind, campaign.status, campaign.scheduled_at, w.bus.sent) == (
        CampaignKind.QUICK,
        CampaignStatus.SCHEDULED,
        NOW + timedelta(hours=2),
        [],
    )


async def test_a_later_quick_send_refuses_a_time_inside_five_minutes() -> None:
    with pytest.raises(BadRequest) as caught:
        await world().service.send_quick(
            PRINCIPAL, quick(TWO_GB, send_at=NOW + timedelta(minutes=4)), NOW
        )
    assert str(caught.value) == SCHEDULE_TOO_SOON


async def test_a_later_quick_send_is_due_for_the_scheduler() -> None:
    w = world()
    result = await w.service.send_quick(
        PRINCIPAL, quick(TWO_GB, send_at=NOW + timedelta(hours=2)), NOW
    )
    due = await w.service.due(NOW + timedelta(hours=2), DUE_LIMIT)
    assert [ref.campaign_id for ref in due] == [result.campaign_id]


async def test_a_later_quick_send_can_be_cancelled_from_the_list() -> None:
    w = world()
    result = await w.service.send_quick(
        PRINCIPAL, quick(TWO_GB, send_at=NOW + timedelta(hours=2)), NOW
    )
    cancelled = await w.service.cancel(PRINCIPAL, result.campaign_id, NOW)
    assert cancelled.status is CampaignStatus.CANCELLED


async def test_settlement_refunds_the_refused_share_once_every_outcome_is_in() -> None:
    w = world()
    result = await sent(w)
    await w.service.record_outcome(ACCOUNT_ID, result.campaign_id, DispatchOutcome.ACCEPTED, NOW)
    await w.service.record_outcome(ACCOUNT_ID, result.campaign_id, DispatchOutcome.REFUSED, NOW)
    assert w.billing.settled == [
        (ACCOUNT_ID, result.campaign_id, Micro(85_400), Micro(GB_RATE), NOW)
    ]


async def test_settlement_marks_the_campaign_sent() -> None:
    w = world()
    result = await sent(w)
    await w.service.record_outcome(ACCOUNT_ID, result.campaign_id, DispatchOutcome.ACCEPTED, NOW)
    await w.service.record_outcome(ACCOUNT_ID, result.campaign_id, DispatchOutcome.ACCEPTED, NOW)
    campaign = stored(w, result.campaign_id)
    assert (campaign.status, campaign.settled_micro, campaign.completed_at) == (
        CampaignStatus.SENT,
        85_400,
        NOW,
    )


async def test_settlement_waits_for_the_last_outcome() -> None:
    w = world()
    result = await sent(w)
    await w.service.record_outcome(ACCOUNT_ID, result.campaign_id, DispatchOutcome.ACCEPTED, NOW)
    assert w.billing.settled == []


async def test_settlement_is_skipped_when_the_flip_is_lost() -> None:
    w = world()
    result = await sent(w)
    await w.service.record_outcome(ACCOUNT_ID, result.campaign_id, DispatchOutcome.ACCEPTED, NOW)
    already = stored(w, result.campaign_id).model_copy(update={"status": CampaignStatus.SENT})
    w.repo.rows[(ACCOUNT_ID, result.campaign_id)] = already

    await w.service.record_outcome(ACCOUNT_ID, result.campaign_id, DispatchOutcome.ACCEPTED, NOW)
    assert w.billing.settled == []


async def test_duplicate_outcome_changes_nothing() -> None:
    w = world()
    result = await sent(w)
    await w.service.record_outcome(ACCOUNT_ID, result.campaign_id, DispatchOutcome.DUPLICATE, NOW)
    assert stored(w, result.campaign_id).counts == CampaignCounts(recipients=2)


@pytest.mark.parametrize(
    ("delivered", "expected"),
    [
        (True, CampaignCounts(recipients=2, delivered=1)),
        (False, CampaignCounts(recipients=2, undelivered=1)),
    ],
    ids=["delivered", "undelivered"],
)
async def test_record_delivery_counts(delivered: bool, expected: CampaignCounts) -> None:
    w = world()
    result = await sent(w)
    await w.service.record_delivery(ACCOUNT_ID, result.campaign_id, delivered=delivered, now=NOW)
    assert stored(w, result.campaign_id).counts == expected


async def test_get_answers_the_stored_campaign() -> None:
    w = world()
    campaign = draft_campaign()
    await w.repo.put_draft(ACCOUNT_ID, campaign)
    assert await w.service.get(ACCOUNT_ID, campaign.campaign_id) == campaign


async def test_get_refuses_an_unknown_campaign() -> None:
    with pytest.raises(NotFound) as caught:
        await world().service.get(ACCOUNT_ID, "missing")
    assert str(caught.value) == CAMPAIGN_NOT_FOUND


async def test_create_draft_stores_a_draft_named_by_the_editor() -> None:
    w = world()
    draft = CampaignDraft(body=BODY, list_id=LIST_ID, name="Helloworld")
    campaign = await w.service.create_draft(PRINCIPAL, draft, NOW)
    assert (campaign.kind, campaign.name, campaign.status) == (
        CampaignKind.LIST,
        "Helloworld",
        CampaignStatus.DRAFT,
    )


async def test_create_draft_fills_the_footer_from_the_opt_out_mode() -> None:
    w = world()
    draft = CampaignDraft(body=BODY, list_id=LIST_ID, name="Helloworld")
    campaign = await w.service.create_draft(PRINCIPAL, draft, NOW)
    assert campaign.footer == REPLY_STOP_FOOTER


async def test_create_draft_shortens_urls_when_the_toggle_is_on() -> None:
    w = world()
    draft = CampaignDraft(body=BODY, list_id=LIST_ID, name="Helloworld", shorten_urls=True)
    campaign = await w.service.create_draft(PRINCIPAL, draft, NOW)
    assert w.links.calls == [(BODY, PRINCIPAL.account_id, campaign.campaign_id)]


async def test_create_draft_leaves_shorten_urls_off_alone() -> None:
    w = world()
    draft = CampaignDraft(body=BODY, list_id=LIST_ID, name="Helloworld")
    await w.service.create_draft(PRINCIPAL, draft, NOW)
    assert w.links.calls == []


async def test_save_draft_replaces_the_stored_draft() -> None:
    w = world()
    campaign = await saved(w, list_campaign())
    draft = CampaignDraft(body="New body", list_id=LIST_ID, name="Renamed")

    updated = await w.service.save_draft(PRINCIPAL, campaign.campaign_id, draft, NOW)
    assert (updated.body, updated.name) == ("New body", "Renamed")


async def test_save_draft_refuses_a_campaign_that_is_no_longer_a_draft() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign(), NOW + timedelta(hours=1))
    with pytest.raises(Conflict) as caught:
        await w.service.save_draft(PRINCIPAL, campaign.campaign_id, CampaignDraft(), NOW)
    assert str(caught.value) == DRAFT_ONLY


async def test_save_draft_refuses_an_unknown_campaign() -> None:
    with pytest.raises(NotFound) as caught:
        await world().service.save_draft(PRINCIPAL, "missing", CampaignDraft(), NOW)
    assert str(caught.value) == CAMPAIGN_NOT_FOUND


async def test_delete_draft_removes_the_row() -> None:
    w = world()
    campaign = await saved(w, list_campaign())
    await w.service.delete_draft(PRINCIPAL, campaign.campaign_id)
    assert w.repo.rows == {}


async def test_delete_draft_refuses_a_scheduled_campaign() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign(), NOW + timedelta(hours=1))
    with pytest.raises(Conflict) as caught:
        await w.service.delete_draft(PRINCIPAL, campaign.campaign_id)
    assert str(caught.value) == DRAFT_ONLY


async def test_quote_of_a_list_prices_recipients_times_parts_times_rate() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    campaign = await saved(w, list_campaign())

    quote = await w.service.quote(PRINCIPAL, campaign.campaign_id, NOW)
    assert (quote.cost_micro, quote.parts, quote.recipients) == (85_400, 1, 2)


async def test_quote_of_a_list_names_the_sender_for_the_confirmation() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await saved(w, list_campaign())

    quote = await w.service.quote(PRINCIPAL, campaign.campaign_id, NOW)
    assert quote.sender_display == "Shared Number"


@pytest.mark.parametrize(
    ("footer", "parts"),
    [(REPLY_STOP_FOOTER, 2), ("", 1)],
    ids=["footer-counts-toward-the-length", "body-alone-is-one-part"],
)
async def test_quote_counts_the_footer_in_the_length(footer: str, parts: int) -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await saved(w, list_campaign(body=ONE_PART_BODY, footer=footer))

    quote = await w.service.quote(PRINCIPAL, campaign.campaign_id, NOW)
    assert quote.parts == parts


async def test_quote_estimates_parts_from_the_longest_resolved_body() -> None:
    members = [contact(GB_ONE, first_name=LONG_NAME), contact(GB_TWO, first_name="Bo")]
    w = world(contacts=contacts_of(members))
    campaign = await saved(w, list_campaign(body="Hi {first_name}"))

    quote = await w.service.quote(PRINCIPAL, campaign.campaign_id, NOW)
    assert quote.parts == 2


async def test_quote_refuses_reply_stop_from_an_alpha_tag() -> None:
    w = world(alpha=True, contacts=contacts_of([contact(GB_ONE)]))
    campaign = await saved(w, list_campaign(opt_out_mode=OptOutMode.REPLY_STOP))

    with pytest.raises(BadRequest) as caught:
        await w.service.quote(PRINCIPAL, campaign.campaign_id, NOW)
    assert str(caught.value) == ALPHA_NEEDS_LINK


async def test_quote_accepts_an_alpha_tag_with_the_unsubscribe_link() -> None:
    w = world(alpha=True, contacts=contacts_of([contact(GB_ONE)]))
    campaign = await saved(
        w, list_campaign(footer=UNSUBSCRIBE_FOOTER, opt_out_mode=OptOutMode.UNSUBSCRIBE_LINK)
    )

    quote = await w.service.quote(PRINCIPAL, campaign.campaign_id, NOW)
    assert quote.recipients == 1


async def test_quote_refuses_a_campaign_without_a_list() -> None:
    w = world()
    campaign = await saved(w, list_campaign().model_copy(update={"list_id": None}))

    with pytest.raises(BadRequest) as caught:
        await w.service.quote(PRINCIPAL, campaign.campaign_id, NOW)
    assert str(caught.value) == NEEDS_LIST


async def test_quote_refuses_an_empty_list() -> None:
    w = world(contacts=contacts_of([]))
    campaign = await saved(w, list_campaign())

    with pytest.raises(BadRequest) as caught:
        await w.service.quote(PRINCIPAL, campaign.campaign_id, NOW)
    assert str(caught.value) == NO_RECIPIENTS


@pytest.mark.parametrize(
    "send_at",
    [NOW + timedelta(minutes=5), NOW + timedelta(days=365), None],
    ids=["five-minutes-ahead", "twelve-months-ahead", "send-now"],
)
async def test_schedule_accepts_the_window(send_at: datetime | None) -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign(), send_at)
    assert (campaign.status, campaign.scheduled_at) == (CampaignStatus.SCHEDULED, send_at or NOW)


@pytest.mark.parametrize(
    ("send_at", "message"),
    [
        (NOW + timedelta(minutes=4, seconds=59), SCHEDULE_TOO_SOON),
        (NOW + timedelta(days=366), SCHEDULE_TOO_LATE),
    ],
    ids=["four-minutes-fifty-nine-refused", "a-day-past-twelve-months-refused"],
)
async def test_schedule_refuses_outside_the_window(send_at: datetime, message: str) -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await saved(w, list_campaign())

    with pytest.raises(BadRequest) as caught:
        await w.service.schedule(PRINCIPAL, campaign.campaign_id, send_at, NOW)
    assert str(caught.value) == message


async def test_schedule_reserves_the_quoted_cost() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    campaign = await scheduled(w, list_campaign())
    assert w.billing.reserved == [(ACCOUNT_ID, Micro(85_400), campaign.campaign_id, NOW)]


async def test_schedule_fixes_the_recipient_count_at_confirmation() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    campaign = await scheduled(w, list_campaign())
    assert campaign.counts.recipients == 2


async def test_schedule_makes_the_campaign_due_at_its_time() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign(), NOW + timedelta(hours=1))

    early = await w.service.due(NOW, DUE_LIMIT)
    late = await w.service.due(NOW + timedelta(hours=1), DUE_LIMIT)
    assert (early, [ref.campaign_id for ref in late]) == ([], [campaign.campaign_id])


async def test_schedule_refuses_a_campaign_that_is_not_a_draft() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign(), NOW + timedelta(hours=1))

    with pytest.raises(Conflict) as caught:
        await w.service.schedule(PRINCIPAL, campaign.campaign_id, None, NOW)
    assert str(caught.value) == DRAFT_ONLY


async def test_cancel_while_scheduled_refunds_the_whole_reservation_once() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    campaign = await scheduled(w, list_campaign(), NOW + timedelta(hours=1))

    await w.service.cancel(PRINCIPAL, campaign.campaign_id, NOW)
    assert w.billing.settled == [(ACCOUNT_ID, campaign.campaign_id, Micro(85_400), Micro(0), NOW)]


async def test_cancel_twice_refunds_once() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign(), NOW + timedelta(hours=1))

    await w.service.cancel(PRINCIPAL, campaign.campaign_id, NOW)
    with pytest.raises(Conflict):
        await w.service.cancel(PRINCIPAL, campaign.campaign_id, NOW)
    assert len(w.billing.settled) == 1


async def test_cancel_takes_the_campaign_out_of_the_due_index() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign(), NOW + timedelta(hours=1))

    await w.service.cancel(PRINCIPAL, campaign.campaign_id, NOW)
    assert await w.service.due(NOW + timedelta(hours=1), DUE_LIMIT) == []


async def test_cancel_while_sending_answers_a_conflict() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await saved(w, list_campaign(status=CampaignStatus.SENDING))

    with pytest.raises(Conflict) as caught:
        await w.service.cancel(PRINCIPAL, campaign.campaign_id, NOW)
    assert str(caught.value) == CAMPAIGN_SENDING


async def test_cancel_of_a_draft_answers_a_conflict() -> None:
    w = world()
    campaign = await saved(w, list_campaign())

    with pytest.raises(Conflict) as caught:
        await w.service.cancel(PRINCIPAL, campaign.campaign_id, NOW)
    assert str(caught.value) == NOT_SCHEDULED


async def test_duplicate_copies_the_campaign_into_a_new_draft() -> None:
    w = world()
    campaign = await saved(w, list_campaign(footer="Bespoke footer"))

    copy = await w.service.duplicate(PRINCIPAL, campaign.campaign_id, NOW)
    assert (copy.name, copy.footer, copy.list_id, copy.status) == (
        f"{campaign.name}{COPY_SUFFIX}",
        "Bespoke footer",
        LIST_ID,
        CampaignStatus.DRAFT,
    )


async def test_duplicate_leaves_the_original_alone() -> None:
    w = world()
    campaign = await saved(w, list_campaign())

    copy = await w.service.duplicate(PRINCIPAL, campaign.campaign_id, NOW)
    assert copy.campaign_id != campaign.campaign_id


async def test_report_answers_the_counts_with_no_clicks_yet() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign())

    report = await w.service.report(PRINCIPAL, campaign.campaign_id)
    assert (report.clicks, report.campaign.counts.recipients) == (0, 1)


async def test_report_answers_the_campaigns_total_clicks() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    w.links.total_clicks = 7
    campaign = await scheduled(w, list_campaign())

    report = await w.service.report(PRINCIPAL, campaign.campaign_id)
    assert report.clicks == 7


async def test_unsubscribe_opts_the_contact_out() -> None:
    w = world()
    token = unsubscribe_token(SECRET, ACCOUNT_ID, GB_ONE)

    await w.service.unsubscribe(token, NOW)
    assert w.contacts.removed == [(ACCOUNT_ID, GB_ONE, NOW)]


async def test_unsubscribe_refuses_a_tampered_token() -> None:
    w = world()
    token = unsubscribe_token(SECRET, ACCOUNT_ID, GB_ONE)

    with pytest.raises(NotFound) as caught:
        await w.service.unsubscribe(f"x{token[1:]}", NOW)
    assert str(caught.value) == UNKNOWN_LINK


async def test_fan_out_queues_one_job_per_recipient() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    campaign = await scheduled(w, list_campaign())

    row = await fanned_out(w, campaign)
    assert (len(jobs_of(w)), row.counts.queued) == (2, 2)


async def test_fan_out_resolves_placeholders_per_recipient() -> None:
    members = [contact(GB_ONE, first_name="Ada"), contact(GB_TWO, first_name="Bo")]
    w = world(contacts=contacts_of(members))
    campaign = await scheduled(w, list_campaign(body="Hi {first_name}", footer=REPLY_STOP_FOOTER))

    await fanned_out(w, campaign)
    assert [job.body for job in jobs_of(w)] == [
        f"Hi Ada\n{REPLY_STOP_FOOTER}",
        f"Hi Bo\n{REPLY_STOP_FOOTER}",
    ]


async def test_fan_out_renders_a_per_recipient_unsubscribe_link() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(
        w, list_campaign(footer=UNSUBSCRIBE_FOOTER, opt_out_mode=OptOutMode.UNSUBSCRIBE_LINK)
    )

    await fanned_out(w, campaign)
    token = unsubscribe_token(SECRET, ACCOUNT_ID, GB_ONE)
    assert jobs_of(w)[0].body == f"{BODY}\nUnsubscribe: {SITE}/api/u/{token}"


async def test_fan_out_carries_the_campaign_ttl() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign())

    await fanned_out(w, campaign)
    assert jobs_of(w)[0].ttl_seconds == CAMPAIGN_TTL_SECONDS


async def test_fan_out_refuses_opted_out_recipients_instead_of_queueing_them() -> None:
    w = world(
        contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)], opted_out=frozenset({GB_ONE}))
    )
    campaign = await scheduled(w, list_campaign())

    row = await fanned_out(w, campaign)
    assert (row.counts.queued, row.counts.refused, [job.to for job in jobs_of(w)]) == (
        1,
        1,
        [GB_TWO],
    )


async def test_fan_out_loads_the_opt_out_set_once() -> None:
    members = [contact(number) for number in gb_numbers(25)]
    w = world(contacts=contacts_of(members))
    campaign = await scheduled(w, list_campaign())

    await fanned_out(w, campaign)
    assert w.contacts.opt_outs_read == [ACCOUNT_ID]


async def test_fan_out_refuses_recipients_outside_the_allowed_countries() -> None:
    w = world(allowed=GB_ONLY, contacts=contacts_of([contact(GB_ONE), contact(FR_ONE)]))
    campaign = await scheduled(w, list_campaign())

    row = await fanned_out(w, campaign)
    assert (row.counts.queued, row.counts.refused, row.counts.recipients) == (1, 1, 2)


async def test_fan_out_sends_in_batches_of_ten_advancing_the_cursor() -> None:
    members = [contact(number) for number in gb_numbers(25)]
    w = world(contacts=contacts_of(members))
    campaign = await scheduled(w, list_campaign())

    await fanned_out(w, campaign)
    assert [len(batch) for _, batch in w.bus.sent] == [10, 10, 5]


async def test_fan_out_clears_the_cursor_and_the_due_index_when_it_finishes() -> None:
    members = [contact(number) for number in gb_numbers(25)]
    w = world(contacts=contacts_of(members))
    campaign = await scheduled(w, list_campaign())

    row = await fanned_out(w, campaign)
    due = await w.service.due(NOW, DUE_LIMIT)
    assert (row.fanout_cursor, due) == (None, [])


async def test_fan_out_resumes_from_the_cursor_after_a_crash() -> None:
    members = [contact(number) for number in gb_numbers(25)]
    w = world(contacts=contacts_of(members))
    campaign = await scheduled(w, list_campaign())
    crashed = stored(w, campaign.campaign_id).model_copy(
        update={
            "claimed_at": NOW - timedelta(minutes=5),
            "counts": stored(w, campaign.campaign_id).counts.model_copy(
                update={"queued": 10, "recipients": 25}
            ),
            "fanout_cursor": "10",
            "status": CampaignStatus.SENDING,
        }
    )
    w.repo.rows[(ACCOUNT_ID, campaign.campaign_id)] = crashed

    (ref,) = await w.service.due(NOW, DUE_LIMIT)
    fanned = await w.service.claim_and_fan_out(ref, NOW)
    assert (fanned.queued, jobs_of(w)[0].to) == (15, gb_numbers(25)[10])


async def test_two_schedulers_claim_one_campaign_once() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    await scheduled(w, list_campaign())
    (ref,) = await w.service.due(NOW, DUE_LIMIT)

    first = await w.service.claim_and_fan_out(ref, NOW)
    second = await w.service.claim_and_fan_out(ref, NOW)
    assert (first.skipped, second.skipped) == (False, True)


async def test_a_lost_claim_queues_nothing() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    await scheduled(w, list_campaign())
    (ref,) = await w.service.due(NOW, DUE_LIMIT)

    await w.service.claim_and_fan_out(ref, NOW)
    await w.service.claim_and_fan_out(ref, NOW)
    assert len(jobs_of(w)) == 1


async def test_fan_out_of_an_empty_list_settles_the_whole_reservation() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign())
    w.contacts.lists = {LIST_ID: []}

    await fanned_out(w, campaign)
    assert w.billing.settled == [(ACCOUNT_ID, campaign.campaign_id, Micro(GB_RATE), Micro(0), NOW)]


async def test_mixed_settlement_bills_what_was_accepted_and_refunds_the_rest_once() -> None:
    members = [
        contact(GB_ONE, first_name=LONG_NAME),
        contact(GB_TWO, first_name="Bo"),
        contact(FR_ONE, first_name="Cy"),
    ]
    w = world(allowed=GB_ONLY, contacts=contacts_of(members))
    campaign = await scheduled(w, list_campaign(body="Hi {first_name}"))
    await fanned_out(w, campaign)

    await w.service.record_outcome(ACCOUNT_ID, campaign.campaign_id, DispatchOutcome.ACCEPTED, NOW)
    await w.service.record_outcome(ACCOUNT_ID, campaign.campaign_id, DispatchOutcome.REFUSED, NOW)
    await w.service.record_delivery(ACCOUNT_ID, campaign.campaign_id, delivered=False, now=NOW)

    assert w.billing.settled == [
        (ACCOUNT_ID, campaign.campaign_id, Micro(170_800), Micro(85_400), NOW)
    ]


async def test_mixed_settlement_carries_each_recipients_own_parts_on_its_job() -> None:
    members = [contact(GB_ONE, first_name=LONG_NAME), contact(GB_TWO, first_name="Bo")]
    w = world(allowed=GB_ONLY, contacts=contacts_of(members))
    campaign = await scheduled(w, list_campaign(body="Hi {first_name}"))

    await fanned_out(w, campaign)
    assert [job.parts for job in jobs_of(w)] == [2, 1]


async def test_a_failed_delivery_after_acceptance_is_not_refunded() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign())
    await fanned_out(w, campaign)

    await w.service.record_outcome(ACCOUNT_ID, campaign.campaign_id, DispatchOutcome.ACCEPTED, NOW)
    await w.service.record_delivery(ACCOUNT_ID, campaign.campaign_id, delivered=False, now=NOW)
    assert w.billing.settled == [
        (ACCOUNT_ID, campaign.campaign_id, Micro(GB_RATE), Micro(GB_RATE), NOW)
    ]


async def stalled(w: World) -> Campaign:
    campaign = await scheduled(w, list_campaign())
    await fanned_out(w, campaign)
    await w.service.record_outcome(ACCOUNT_ID, campaign.campaign_id, DispatchOutcome.ACCEPTED, NOW)
    return campaign


async def test_a_campaign_still_making_progress_is_not_swept() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    await stalled(w)
    assert await w.service.stuck(NOW + STUCK_AFTER, DUE_LIMIT) == []


async def test_a_campaign_whose_last_outcome_is_older_than_the_deadline_is_swept() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    campaign = await stalled(w)

    swept = await w.service.stuck(NOW + STUCK_AFTER + timedelta(milliseconds=1), DUE_LIMIT)
    assert [ref.campaign_id for ref in swept] == [campaign.campaign_id]


async def test_sweeping_a_stuck_campaign_bills_what_was_sent_and_refunds_the_rest() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    campaign = await stalled(w)
    later = NOW + timedelta(hours=2)
    (ref,) = await w.service.stuck(later, DUE_LIMIT)

    settled = await w.service.settle_stuck(ref, later)
    assert (settled.missing, settled.settled_micro, w.billing.settled) == (
        1,
        Micro(GB_RATE),
        [(ACCOUNT_ID, campaign.campaign_id, Micro(85_400), Micro(GB_RATE), later)],
    )


async def test_sweeping_a_stuck_campaign_refunds_once() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    await stalled(w)
    later = NOW + timedelta(hours=2)
    (ref,) = await w.service.stuck(later, DUE_LIMIT)

    await w.service.settle_stuck(ref, later)
    second = await w.service.settle_stuck(ref, later)
    assert (second.skipped, len(w.billing.settled)) == (True, 1)


async def test_sweeping_marks_the_campaign_sent_and_leaves_the_index() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    campaign = await stalled(w)
    later = NOW + timedelta(hours=2)
    (ref,) = await w.service.stuck(later, DUE_LIMIT)

    await w.service.settle_stuck(ref, later)
    assert (
        stored(w, campaign.campaign_id).status,
        await w.service.stuck(later, DUE_LIMIT),
    ) == (CampaignStatus.SENT, [])


async def test_a_late_outcome_after_a_sweep_does_not_refund_again() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    campaign = await stalled(w)
    later = NOW + timedelta(hours=2)
    (ref,) = await w.service.stuck(later, DUE_LIMIT)
    await w.service.settle_stuck(ref, later)

    await w.service.record_outcome(
        ACCOUNT_ID, campaign.campaign_id, DispatchOutcome.ACCEPTED, later
    )
    assert len(w.billing.settled) == 1


async def test_a_campaign_that_finished_early_is_taken_off_the_sending_index() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign())
    await fanned_out(w, campaign)
    await w.service.record_outcome(ACCOUNT_ID, campaign.campaign_id, DispatchOutcome.ACCEPTED, NOW)
    w.repo.sending_keys.add((ACCOUNT_ID, campaign.campaign_id))
    later = NOW + timedelta(hours=2)

    (ref,) = await w.service.stuck(later, DUE_LIMIT)
    settled = await w.service.settle_stuck(ref, later)
    assert (settled.skipped, await w.service.stuck(later, DUE_LIMIT)) == (True, [])


async def test_quote_refuses_a_number_that_opted_out() -> None:
    w = world(contacts=contacts_of(opted_out=frozenset({GB_ONE})))
    quote = await w.service.quote_quick(PRINCIPAL, quick(TWO_GB), NOW)
    assert (quote.recipients, quote.cost_micro, quote.refused) == (
        1,
        GB_RATE,
        [Refusal(message=OPTED_OUT_MESSAGE, reason=RefusalReason.OPTED_OUT, to=GB_ONE)],
    )


async def test_quote_reads_the_opt_out_set_once() -> None:
    w = world()
    await w.service.quote_quick(PRINCIPAL, quick([GB_ONE, US_ONE, GB_TWO]), NOW)
    assert w.contacts.opt_outs_read == [ACCOUNT_ID]


async def test_send_enqueues_nothing_for_a_number_that_opted_out() -> None:
    w = world(contacts=contacts_of(opted_out=frozenset({GB_ONE})))
    await sent(w)
    assert [job.to for job in jobs_of(w)] == [GB_TWO]


async def test_quote_takes_a_list_as_a_recipient() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    quote = await w.service.quote_quick(PRINCIPAL, listed([]), NOW)
    assert (quote.recipients, quote.cost_micro) == (2, 85_400)


async def test_a_number_already_in_the_list_is_sent_to_once() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    await w.service.send_quick(PRINCIPAL, listed([GB_ONE]), NOW)
    assert [job.to for job in jobs_of(w)] == [GB_ONE, GB_TWO]


async def test_a_contact_in_the_list_that_opted_out_is_refused() -> None:
    members = [contact(GB_ONE), contact(GB_TWO)]
    w = world(contacts=contacts_of(members, opted_out=frozenset({GB_ONE})))
    quote = await w.service.quote_quick(PRINCIPAL, listed([]), NOW)
    assert (quote.recipients, quote.cost_micro, quote.refused) == (
        1,
        GB_RATE,
        [Refusal(message=OPTED_OUT_MESSAGE, reason=RefusalReason.OPTED_OUT, to=GB_ONE)],
    )


@pytest.mark.parametrize(
    ("listed_members", "typed"),
    [(MAX_RECIPIENTS, 0), (MAX_RECIPIENTS - 1, 1)],
    ids=["a-thousand-from-one-list", "a-thousand-across-a-list-and-a-number"],
)
async def test_the_merged_total_accepts_a_thousand(listed_members: int, typed: int) -> None:
    numbers = gb_numbers(MAX_RECIPIENTS)
    w = world(contacts=contacts_of([contact(number) for number in numbers[:listed_members]]))

    quote = await w.service.quote_quick(PRINCIPAL, listed(numbers[listed_members:][:typed]), NOW)
    assert quote.recipients == listed_members + typed


async def test_the_merged_total_refuses_a_thousand_and_one() -> None:
    numbers = gb_numbers(MAX_RECIPIENTS + 1)
    w = world(contacts=contacts_of([contact(number) for number in numbers[:MAX_RECIPIENTS]]))

    with pytest.raises(BadRequest) as caught:
        await w.service.quote_quick(PRINCIPAL, listed(numbers[MAX_RECIPIENTS:]), NOW)
    assert str(caught.value) == TOO_MANY_RECIPIENTS


async def test_an_unknown_list_is_refused() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    request = QuickSendRequest(body=BODY, list_ids=["missing"], to=[])

    with pytest.raises(NotFound) as caught:
        await w.service.quote_quick(PRINCIPAL, request, NOW)
    assert str(caught.value) == LIST_NOT_FOUND


async def test_send_resolves_a_placeholder_per_recipient_from_a_list() -> None:
    members = [contact(GB_ONE, first_name="Ada"), contact(GB_TWO, first_name="Bo")]
    w = world(contacts=contacts_of(members))

    await w.service.send_quick(PRINCIPAL, personal([]), NOW)
    assert [job.body for job in jobs_of(w)] == ["Hi Ada", "Hi Bo"]


async def test_send_resolves_a_known_placeholder_to_empty_for_a_typed_number() -> None:
    w = world()
    request = QuickSendRequest(body="Hi {first_name}", to=[GB_ONE])

    await w.service.send_quick(PRINCIPAL, request, NOW)
    assert [job.body for job in jobs_of(w)] == ["Hi "]


async def test_a_number_in_both_a_list_and_the_typed_entries_is_personalised_once() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE, first_name="Ada")]))

    await w.service.send_quick(PRINCIPAL, personal([GB_ONE]), NOW)
    assert [job.body for job in jobs_of(w)] == ["Hi Ada"]


async def test_a_quick_quote_estimates_parts_from_the_longest_resolved_body() -> None:
    members = [contact(GB_ONE, first_name=LONG_NAME), contact(GB_TWO, first_name="Bo")]
    w = world(contacts=contacts_of(members))

    quote = await w.service.quote_quick(PRINCIPAL, personal([]), NOW)
    assert (quote.parts, quote.cost_micro) == (2, GB_RATE * 2 * 2)


async def test_a_quick_job_carries_its_own_resolved_parts() -> None:
    members = [contact(GB_ONE, first_name=LONG_NAME), contact(GB_TWO, first_name="Bo")]
    w = world(contacts=contacts_of(members))

    await w.service.send_quick(PRINCIPAL, personal([]), NOW)
    assert [job.parts for job in jobs_of(w)] == [2, 1]


async def test_a_later_quick_send_keeps_its_personalisation() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE, first_name="Ada")]))
    result = await w.service.send_quick(
        PRINCIPAL, personal([], send_at=NOW + timedelta(hours=2)), NOW
    )
    later = NOW + timedelta(hours=2)

    (ref,) = await w.service.due(later, DUE_LIMIT)
    await w.service.claim_and_fan_out(ref, later)
    assert (result.recipients, [job.body for job in jobs_of(w)]) == (1, ["Hi Ada"])


LONG_MMS_BODY = "A" * 140
LINKED_MMS_BODY = f"{LONG_MMS_BODY}\n\n{MEDIA_URL}"
LINKED_MMS_PARTS = segments_of(LINKED_MMS_BODY, encoding_of(LINKED_MMS_BODY))


def mms_quick(
    to: Sequence[str], body: str = BODY, media_key: str | None = MEDIA_KEY, subject: str = ""
) -> QuickSendRequest:
    return QuickSendRequest(
        body=body, kind=Product.MMS, media_key=media_key, subject=subject, to=list(to)
    )


@pytest.mark.parametrize(
    ("product", "expected"),
    [
        (Product.SMS, BODY),
        (Product.MMS, BODY),
        (Product.MMS_AS_LINK, f"{BODY}\n\n{MEDIA_URL}"),
    ],
    ids=["sms-is-unchanged", "mms-is-unchanged", "mms-as-link-appends-the-media-url"],
)
def test_with_media_link(product: Product, expected: str) -> None:
    assert with_media_link(BODY, product, MEDIA_URL) == expected


@pytest.mark.parametrize(
    ("product", "expected"),
    [(Product.SMS, 3), (Product.MMS, 1), (Product.MMS_AS_LINK, 7)],
    ids=[
        "sms-uses-the-quoted-parts",
        "mms-is-always-one-part",
        "mms-as-link-uses-the-linked-parts",
    ],
)
def test_billed_parts(product: Product, expected: int) -> None:
    quote = BodyQuote(chars=1, encoding=Encoding.GSM7, parts=3)
    assert billed_parts(product, quote, link_parts=7) == expected


@pytest.mark.parametrize(
    ("product", "expected"),
    [(Product.SMS, Product.SMS), (Product.MMS, Product.MMS), (Product.MMS_AS_LINK, Product.SMS)],
    ids=["sms-rates-as-sms", "mms-rates-as-mms", "mms-as-link-rates-as-sms"],
)
def test_rate_product_of(product: Product, expected: Product) -> None:
    assert rate_product_of(product) is expected


def test_parts_of_an_mms_is_always_one() -> None:
    assert parts_of(Product.MMS, "a" * 400, Encoding.GSM7) == 1


def test_parts_of_an_sms_counts_segments() -> None:
    assert parts_of(Product.SMS, "a" * 306, Encoding.GSM7) == 2


async def test_quick_mms_requires_an_attached_image() -> None:
    with pytest.raises(BadRequest) as caught:
        await world().service.quote_quick(PRINCIPAL, mms_quick([GB_ONE], media_key=None), NOW)
    assert str(caught.value) == NEEDS_MEDIA


async def test_quick_mms_to_the_united_states_is_billed_as_one_flat_mms() -> None:
    quote = await world().service.quote_quick(PRINCIPAL, mms_quick([US_ONE]), NOW)
    assert (quote.cost_micro, quote.parts, quote.recipients) == (150_000, 1, 1)


async def test_quick_mms_outside_us_ca_is_billed_as_a_linked_text() -> None:
    quote = await world().service.quote_quick(
        PRINCIPAL, mms_quick([GB_ONE], body=LONG_MMS_BODY), NOW
    )
    assert quote.cost_micro == GB_RATE * LINKED_MMS_PARTS


async def test_quick_mms_prices_a_mixed_country_send_per_recipient() -> None:
    quote = await world().service.quote_quick(
        PRINCIPAL, mms_quick([US_ONE, GB_ONE], body=LONG_MMS_BODY), NOW
    )
    assert quote.cost_micro == 150_000 + GB_RATE * LINKED_MMS_PARTS


async def test_send_quick_mms_carries_the_media_key_and_subject_to_the_united_states() -> None:
    w = world()
    await w.service.send_quick(PRINCIPAL, mms_quick([US_ONE], subject="Look at this"), NOW)

    (job,) = jobs_of(w)
    assert (job.product, job.body, job.media_key, job.subject, job.parts) == (
        Product.MMS,
        BODY,
        MEDIA_KEY,
        "Look at this",
        1,
    )


async def test_send_quick_mms_sends_a_link_outside_the_united_states_and_canada() -> None:
    w = world()
    await w.service.send_quick(PRINCIPAL, mms_quick([GB_ONE], body=LONG_MMS_BODY), NOW)

    (job,) = jobs_of(w)
    assert (job.product, job.body, job.media_key, job.subject, job.parts) == (
        Product.MMS_AS_LINK,
        LINKED_MMS_BODY,
        None,
        "",
        LINKED_MMS_PARTS,
    )


def mms_campaign(
    body: str = BODY, media_key: str | None = MEDIA_KEY, subject: str | None = None
) -> Campaign:
    return list_campaign(body=body).model_copy(
        update={"channel": Product.MMS, "media_key": media_key, "subject": subject}
    )


async def test_quote_of_an_mms_campaign_without_media_needs_one() -> None:
    w = world()
    campaign = await saved(w, mms_campaign(body="", media_key=None))

    with pytest.raises(BadRequest) as caught:
        await w.service.quote(PRINCIPAL, campaign.campaign_id, NOW)
    assert str(caught.value) == NEEDS_MEDIA


async def test_quote_of_an_mms_campaign_with_a_body_still_needs_media() -> None:
    w = world()
    campaign = await saved(w, mms_campaign(body=BODY, media_key=None))

    with pytest.raises(BadRequest) as caught:
        await w.service.quote(PRINCIPAL, campaign.campaign_id, NOW)
    assert str(caught.value) == NEEDS_MEDIA


async def test_quote_of_an_sms_campaign_still_needs_a_body() -> None:
    w = world()
    campaign = await saved(w, list_campaign(body=""))

    with pytest.raises(BadRequest) as caught:
        await w.service.quote(PRINCIPAL, campaign.campaign_id, NOW)
    assert str(caught.value) == NEEDS_BODY


async def test_quote_of_an_mms_campaign_accepts_media_with_no_text() -> None:
    w = world(contacts=contacts_of([contact(US_ONE)]))
    campaign = await saved(w, mms_campaign(body=""))

    quote = await w.service.quote(PRINCIPAL, campaign.campaign_id, NOW)
    assert (quote.cost_micro, quote.parts) == (150_000, 1)


async def test_quote_of_an_mms_campaign_prices_a_mixed_country_list() -> None:
    w = world(contacts=contacts_of([contact(US_ONE), contact(GB_ONE)]))
    campaign = await saved(w, mms_campaign(body=LONG_MMS_BODY))

    quote = await w.service.quote(PRINCIPAL, campaign.campaign_id, NOW)
    assert quote.cost_micro == 150_000 + GB_RATE * LINKED_MMS_PARTS


async def test_fan_out_of_an_mms_campaign_dispatches_media_to_the_united_states() -> None:
    w = world(contacts=contacts_of([contact(US_ONE)]))
    campaign = await scheduled(w, mms_campaign(body=BODY, subject="Sale"))

    await fanned_out(w, campaign)
    (job,) = jobs_of(w)
    assert (job.product, job.body, job.media_key, job.subject, job.parts) == (
        Product.MMS,
        BODY,
        MEDIA_KEY,
        "Sale",
        1,
    )


async def test_fan_out_of_an_mms_campaign_sends_a_link_outside_us_ca() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, mms_campaign(body=LONG_MMS_BODY))

    await fanned_out(w, campaign)
    (job,) = jobs_of(w)
    assert (job.product, job.body, job.media_key, job.parts) == (
        Product.MMS_AS_LINK,
        LINKED_MMS_BODY,
        None,
        LINKED_MMS_PARTS,
    )


async def test_fan_out_of_a_mixed_country_mms_campaign_resolves_each_recipient_on_its_own() -> None:
    w = world(contacts=contacts_of([contact(US_ONE), contact(GB_ONE)]))
    campaign = await scheduled(w, mms_campaign(body=LONG_MMS_BODY))

    await fanned_out(w, campaign)
    products = sorted(job.product for job in jobs_of(w))
    assert products == sorted([Product.MMS, Product.MMS_AS_LINK])


def abandoned(w: World, campaign: Campaign, claimed_at: datetime) -> None:
    w.repo.rows[(ACCOUNT_ID, campaign.campaign_id)] = stored(w, campaign.campaign_id).model_copy(
        update={"claimed_at": claimed_at, "fanout_cursor": "0", "status": CampaignStatus.SENDING}
    )


@pytest.mark.parametrize(
    ("age", "refunds"),
    [(STUCK_AFTER, 1), (STUCK_AFTER - timedelta(milliseconds=1), 0)],
    ids=["claimed-an-hour-ago-is-abandoned", "claimed-just-under-an-hour-ago-resumes"],
)
async def test_claim_and_fan_out_settles_only_an_abandoned_fan_out(
    age: timedelta, refunds: int
) -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign())
    later = NOW + STUCK_AFTER
    abandoned(w, campaign, later - age)

    (ref,) = await w.service.due(later, DUE_LIMIT)
    await w.service.claim_and_fan_out(ref, later)

    assert len(w.billing.settled) == refunds


async def test_an_abandoned_fan_out_refunds_the_whole_reservation() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign())
    later = NOW + STUCK_AFTER
    abandoned(w, campaign, NOW)

    (ref,) = await w.service.due(later, DUE_LIMIT)
    await w.service.claim_and_fan_out(ref, later)

    assert w.billing.settled == [
        (ACCOUNT_ID, campaign.campaign_id, Micro(GB_RATE), Micro(0), later)
    ]


async def test_an_abandoned_fan_out_leaves_the_due_index() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = await scheduled(w, list_campaign())
    later = NOW + STUCK_AFTER
    abandoned(w, campaign, NOW)

    (ref,) = await w.service.due(later, DUE_LIMIT)
    await w.service.claim_and_fan_out(ref, later)

    assert await w.service.due(later, DUE_LIMIT) == []


async def unsettled(w: World) -> Campaign:
    campaign = await scheduled(w, list_campaign())
    await fanned_out(w, campaign)
    await w.service.record_outcome(ACCOUNT_ID, campaign.campaign_id, DispatchOutcome.ACCEPTED, NOW)
    w.billing.settle_failures = 1
    with pytest.raises(Internal):
        await w.service.record_outcome(
            ACCOUNT_ID, campaign.campaign_id, DispatchOutcome.REFUSED, NOW
        )
    return campaign


async def test_a_campaign_whose_settle_failed_stays_on_the_sending_index() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    campaign = await unsettled(w)
    later = NOW + timedelta(hours=2)

    swept = await w.service.stuck(later, DUE_LIMIT)

    assert [ref.campaign_id for ref in swept] == [campaign.campaign_id]


async def test_sweeping_a_campaign_whose_settle_failed_retries_the_refund() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    campaign = await unsettled(w)
    later = NOW + timedelta(hours=2)
    (ref,) = await w.service.stuck(later, DUE_LIMIT)

    await w.service.settle_stuck(ref, later)

    assert w.billing.settled == [
        (ACCOUNT_ID, campaign.campaign_id, Micro(85_400), Micro(GB_RATE), later)
    ]


async def test_a_redriven_settlement_records_the_settled_amount() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    campaign = await unsettled(w)
    later = NOW + timedelta(hours=2)
    (ref,) = await w.service.stuck(later, DUE_LIMIT)

    await w.service.settle_stuck(ref, later)

    assert stored(w, campaign.campaign_id).settled_micro == GB_RATE


async def test_a_redriven_settlement_refunds_once() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    await unsettled(w)
    later = NOW + timedelta(hours=2)
    (ref,) = await w.service.stuck(later, DUE_LIMIT)

    await w.service.settle_stuck(ref, later)
    second = await w.service.settle_stuck(ref, later)

    assert (second.skipped, len(w.billing.settled)) == (True, 1)

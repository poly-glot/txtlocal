from datetime import timedelta

import pytest

from txtlocal.shared.errors import AppError, BadRequest, Conflict, NotFound, PaymentRequired
from txtlocal.shared.money import Micro
from txtlocal.shared.phone import INVALID_NUMBER_MESSAGE
from txtlocal.slices.senders.model import (
    SHARED_DISPLAY,
    SHARED_VALUE,
    AlphaTagRequest,
    Channel,
    NumberSearchQuery,
    OwnNumberRequest,
    Sender,
    SenderKind,
    SenderStatus,
    SmartSenderRequest,
    UseCase,
    UseFor,
    VerificationRequest,
    display_of,
    status_label_of,
)
from txtlocal.slices.senders.service import (
    ALPHA_TAG_INVALID,
    CODE_INCORRECT,
    ENTER_CODE,
    NUMBER_ALREADY_ADDED,
    NUMBER_NOT_FOUND,
    ONLY_OWN_OR_DEDICATED_REMOVABLE,
    RENEWAL_PERIOD,
    SENDER_NOT_FOUND,
    SHARED_POOL_IDENTITY,
    TOP_UP_TO_RENT,
    SendersService,
    is_ready_for,
    is_six_digits,
    is_valid_alpha_tag,
)
from txtlocal.slices.senders.tests.fakes import (
    ACCOUNT,
    ALPHA_TAG,
    CODE,
    DEDICATED_NUMBER,
    NOW,
    OWN_NUMBER,
    SECOND_NUMBER,
    InMemorySendersRepo,
    ScriptedBilling,
    ScriptedVerification,
    sender_of,
)


@pytest.mark.parametrize(
    ("kind", "value", "expected"),
    [
        (SenderKind.ALPHA, "TXTLOCAL", "TXTLOCAL"),
        (SenderKind.DEDICATED, "+447984390718", "+447984390718"),
        (SenderKind.OWN, OWN_NUMBER, "+447411972333 (Own Number)"),
        (SenderKind.SHARED, SHARED_VALUE, "Shared Number"),
    ],
    ids=["alpha-is-the-tag", "dedicated-is-the-number", "own-is-labelled", "shared-is-named"],
)
def test_display_of(kind: SenderKind, value: str, expected: str) -> None:
    assert display_of(sender_of(kind, value)) == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (SenderStatus.PENDING_VERIFICATION, "Pending verification"),
        (SenderStatus.PROVISIONING, "Provisioning"),
        (SenderStatus.READY, "Ready to use"),
        (SenderStatus.REJECTED, "Rejected"),
        (SenderStatus.UNDER_REVIEW, "Under review"),
    ],
    ids=["pending", "provisioning", "ready", "rejected", "under-review"],
)
def test_status_label_of(status: SenderStatus, expected: str) -> None:
    assert status_label_of(status) == expected


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("123456", True),
        ("12345", False),
        ("1234567", False),
        ("12345a", False),
        ("١٢٣٤٥٦", False),
    ],
    ids=["six-digits", "five-digits", "seven-digits", "letter", "non-ascii-digits"],
)
def test_is_six_digits(code: str, expected: bool) -> None:
    assert is_six_digits(code) is expected


@pytest.mark.parametrize(
    ("status", "country", "expected"),
    [
        (SenderStatus.READY, "GB", True),
        (SenderStatus.READY, "US", False),
        (SenderStatus.PENDING_VERIFICATION, "GB", False),
    ],
    ids=["ready-in-country", "ready-elsewhere", "pending-in-country"],
)
def test_is_ready_for(status: SenderStatus, country: str, expected: bool) -> None:
    assert is_ready_for(sender_of(SenderKind.OWN, OWN_NUMBER, status=status), country) is expected


@pytest.mark.usefixtures("provisioned")
async def test_provision_defaults_creates_the_shared_sender_and_its_smart_pointer(
    repo: InMemorySendersRepo,
) -> None:
    [shared] = await repo.list_senders(ACCOUNT)
    [smart] = await repo.list_smart(ACCOUNT)

    assert (shared.kind, shared.status, shared.country, shared.value) == (
        SenderKind.SHARED,
        SenderStatus.READY,
        "GB",
        SHARED_VALUE,
    )
    assert shared.capabilities == (Channel.MMS, Channel.SMS)
    assert shared.provider_identity == SHARED_POOL_IDENTITY
    assert shared.created_at == NOW
    assert display_of(shared) == SHARED_DISPLAY
    assert (smart.country, smart.sender_id, smart.channel) == ("GB", shared.sender_id, Channel.SMS)


async def test_provision_defaults_twice_keeps_the_first_shared_sender(
    provisioned: SendersService, repo: InMemorySendersRepo, shared_sender: Sender
) -> None:
    await provisioned.provision_defaults(ACCOUNT, NOW)

    assert await repo.list_senders(ACCOUNT) == [shared_sender]


async def test_resolve_without_a_sender_returns_the_smart_sender(
    provisioned: SendersService, shared_sender: Sender
) -> None:
    assert await provisioned.resolve(ACCOUNT, None, "GB") == shared_sender


async def test_resolve_follows_a_changed_smart_sender(
    provisioned: SendersService, verified_number: Sender
) -> None:
    await provisioned.set_smart(
        ACCOUNT, "GB", SmartSenderRequest(sender_id=verified_number.sender_id)
    )

    assert await provisioned.resolve(ACCOUNT, None, "GB") == verified_number


async def test_resolve_refuses_a_country_without_a_smart_sender(
    provisioned: SendersService,
) -> None:
    with pytest.raises(BadRequest) as caught:
        await provisioned.resolve(ACCOUNT, None, "US")
    assert str(caught.value) == "Sending to US is not enabled for this account"


async def test_resolve_returns_a_named_ready_sender(
    provisioned: SendersService, verified_number: Sender
) -> None:
    assert await provisioned.resolve(ACCOUNT, verified_number.sender_id, "GB") == verified_number


@pytest.mark.parametrize(
    ("chosen", "country", "error", "message"),
    [
        ("shared", "US", BadRequest, "Shared Number is not ready to send to US"),
        ("pending", "GB", BadRequest, "+447411972333 (Own Number) is not ready to send to GB"),
        ("missing", "GB", NotFound, SENDER_NOT_FOUND),
    ],
    ids=["shared-outside-its-country", "pending-own-number", "unknown-sender"],
)
async def test_resolve_refuses_a_named_sender(
    provisioned: SendersService,
    sender_ids: dict[str, str],
    chosen: str,
    country: str,
    error: type[AppError],
    message: str,
) -> None:
    with pytest.raises(error) as caught:
        await provisioned.resolve(ACCOUNT, sender_ids[chosen], country)
    assert str(caught.value) == message


async def test_verified_numbers_holds_ready_own_numbers_only(
    provisioned: SendersService, verified_number: Sender, verified_us_number: Sender
) -> None:
    pending = await provisioned.add_own(ACCOUNT, OwnNumberRequest(number=SECOND_NUMBER))

    numbers = await provisioned.verified_numbers(ACCOUNT)

    assert numbers == frozenset({verified_number.value, verified_us_number.value})
    assert pending.value not in numbers


async def test_add_own_creates_a_pending_sender_and_starts_verification(
    pending_number: Sender, repo: InMemorySendersRepo, gateway: ScriptedVerification
) -> None:
    assert (pending_number.kind, pending_number.status, pending_number.country) == (
        SenderKind.OWN,
        SenderStatus.PENDING_VERIFICATION,
        "GB",
    )
    assert (pending_number.value, pending_number.nickname) == (OWN_NUMBER, "Sam's Phone")
    assert pending_number.capabilities == (Channel.SMS,)
    assert pending_number.provider_identity is None
    assert pending_number.verified_at is None
    assert display_of(pending_number) == "+447411972333 (Own Number)"
    assert await repo.get_sender(ACCOUNT, pending_number.sender_id) == pending_number
    assert gateway.started == [OWN_NUMBER]


async def test_add_own_refuses_a_number_that_does_not_parse(provisioned: SendersService) -> None:
    with pytest.raises(BadRequest) as caught:
        await provisioned.add_own(ACCOUNT, OwnNumberRequest(number="not a number"))
    assert str(caught.value) == INVALID_NUMBER_MESSAGE


async def test_add_own_again_resends_the_code_to_the_pending_number(
    provisioned: SendersService,
    pending_number: Sender,
    repo: InMemorySendersRepo,
    gateway: ScriptedVerification,
) -> None:
    again = await provisioned.add_own(ACCOUNT, OwnNumberRequest(number=OWN_NUMBER))

    assert again == pending_number
    assert len(await repo.list_senders(ACCOUNT)) == 2
    assert gateway.started == [OWN_NUMBER, OWN_NUMBER]


@pytest.mark.usefixtures("verified_number")
async def test_add_own_refuses_a_number_already_verified(provisioned: SendersService) -> None:
    with pytest.raises(Conflict) as caught:
        await provisioned.add_own(ACCOUNT, OwnNumberRequest(number=OWN_NUMBER))
    assert str(caught.value) == NUMBER_ALREADY_ADDED


async def test_verify_own_flips_the_number_to_ready(
    verified_number: Sender, pending_number: Sender, repo: InMemorySendersRepo
) -> None:
    assert (verified_number.status, verified_number.verified_at) == (SenderStatus.READY, NOW)
    assert verified_number.sender_id == pending_number.sender_id
    assert await repo.get_sender(ACCOUNT, pending_number.sender_id) == verified_number


@pytest.mark.parametrize(
    ("chosen", "code", "error", "message"),
    [
        ("pending", "12345", BadRequest, ENTER_CODE),
        ("pending", "654321", BadRequest, CODE_INCORRECT),
        ("shared", CODE, NotFound, SENDER_NOT_FOUND),
        ("missing", CODE, NotFound, SENDER_NOT_FOUND),
    ],
    ids=["short-code", "wrong-code", "shared-sender", "unknown-sender"],
)
async def test_verify_own_refuses(
    provisioned: SendersService,
    sender_ids: dict[str, str],
    chosen: str,
    code: str,
    error: type[AppError],
    message: str,
) -> None:
    with pytest.raises(error) as caught:
        await provisioned.verify_own(ACCOUNT, sender_ids[chosen], VerificationRequest(code=code))
    assert str(caught.value) == message


async def test_verify_own_with_a_wrong_code_leaves_the_number_pending(
    provisioned: SendersService, pending_number: Sender, repo: InMemorySendersRepo
) -> None:
    with pytest.raises(BadRequest):
        await provisioned.verify_own(
            ACCOUNT, pending_number.sender_id, VerificationRequest(code="654321")
        )

    assert await repo.get_sender(ACCOUNT, pending_number.sender_id) == pending_number


async def test_set_smart_points_the_country_at_a_ready_sender(
    provisioned: SendersService, verified_number: Sender, repo: InMemorySendersRepo
) -> None:
    smart = await provisioned.set_smart(
        ACCOUNT, "GB", SmartSenderRequest(sender_id=verified_number.sender_id)
    )

    assert (smart.country, smart.sender_id) == ("GB", verified_number.sender_id)
    assert await repo.list_smart(ACCOUNT) == [smart]


@pytest.mark.parametrize(
    ("chosen", "country", "error", "message"),
    [
        ("pending", "GB", BadRequest, "+447411972333 (Own Number) is not ready to send to GB"),
        ("us", "US", BadRequest, "Sending to US is not enabled for this account"),
        ("us", "GB", BadRequest, "+12025550123 (Own Number) is not ready to send to GB"),
        ("missing", "GB", NotFound, SENDER_NOT_FOUND),
    ],
    ids=["pending-own-number", "country-without-shared-sender", "wrong-country", "unknown"],
)
async def test_set_smart_refuses(
    provisioned: SendersService,
    sender_ids: dict[str, str],
    chosen: str,
    country: str,
    error: type[AppError],
    message: str,
) -> None:
    with pytest.raises(error) as caught:
        await provisioned.set_smart(
            ACCOUNT, country, SmartSenderRequest(sender_id=sender_ids[chosen])
        )
    assert str(caught.value) == message


async def test_set_smart_refusal_leaves_the_smart_sender_unchanged(
    provisioned: SendersService,
    shared_sender: Sender,
    pending_number: Sender,
    repo: InMemorySendersRepo,
) -> None:
    with pytest.raises(BadRequest):
        await provisioned.set_smart(
            ACCOUNT, "GB", SmartSenderRequest(sender_id=pending_number.sender_id)
        )

    assert [smart.sender_id for smart in await repo.list_smart(ACCOUNT)] == [
        shared_sender.sender_id
    ]


async def test_remove_deletes_the_own_number_and_repoints_its_smart_country_to_shared(
    provisioned: SendersService,
    shared_sender: Sender,
    verified_number: Sender,
    repo: InMemorySendersRepo,
) -> None:
    await provisioned.set_smart(
        ACCOUNT, "GB", SmartSenderRequest(sender_id=verified_number.sender_id)
    )

    await provisioned.remove(ACCOUNT, verified_number.sender_id)

    assert await repo.list_senders(ACCOUNT) == [shared_sender]
    assert [smart.sender_id for smart in await repo.list_smart(ACCOUNT)] == [
        shared_sender.sender_id
    ]


async def test_remove_leaves_a_smart_country_that_pointed_elsewhere(
    provisioned: SendersService,
    shared_sender: Sender,
    verified_number: Sender,
    repo: InMemorySendersRepo,
) -> None:
    await provisioned.remove(ACCOUNT, verified_number.sender_id)

    assert [smart.sender_id for smart in await repo.list_smart(ACCOUNT)] == [
        shared_sender.sender_id
    ]


@pytest.mark.parametrize(
    ("chosen", "error", "message"),
    [
        ("shared", BadRequest, ONLY_OWN_OR_DEDICATED_REMOVABLE),
        ("missing", NotFound, SENDER_NOT_FOUND),
    ],
    ids=["shared-sender", "unknown-sender"],
)
async def test_remove_refuses(
    provisioned: SendersService,
    shared_sender: Sender,
    repo: InMemorySendersRepo,
    chosen: str,
    error: type[AppError],
    message: str,
) -> None:
    sender_id = {"missing": "no-such-sender", "shared": shared_sender.sender_id}[chosen]

    with pytest.raises(error) as caught:
        await provisioned.remove(ACCOUNT, sender_id)
    assert str(caught.value) == message
    assert await repo.list_senders(ACCOUNT) == [shared_sender]


async def test_remove_refuses_an_alpha_tag(provisioned: SendersService) -> None:
    tag = await provisioned.register_alpha(
        ACCOUNT, AlphaTagRequest(country="GB", tag=ALPHA_TAG, use_case=UseCase.MARKETING)
    )

    with pytest.raises(BadRequest) as caught:
        await provisioned.remove(ACCOUNT, tag.sender_id)
    assert str(caught.value) == ONLY_OWN_OR_DEDICATED_REMOVABLE


async def test_remove_cancels_a_dedicated_number_instead_of_deleting_it(
    provisioned: SendersService, repo: InMemorySendersRepo
) -> None:
    dedicated = await provisioned.buy_number(ACCOUNT, DEDICATED_NUMBER)

    await provisioned.remove(ACCOUNT, dedicated.sender_id)

    after = await repo.get_sender(ACCOUNT, dedicated.sender_id)
    assert after is not None
    assert (after.cancelled, after.status) == (True, SenderStatus.READY)


async def test_remove_of_a_cancelled_dedicated_number_is_idempotent(
    provisioned: SendersService, repo: InMemorySendersRepo
) -> None:
    dedicated = await provisioned.buy_number(ACCOUNT, DEDICATED_NUMBER)
    await provisioned.remove(ACCOUNT, dedicated.sender_id)

    await provisioned.remove(ACCOUNT, dedicated.sender_id)

    after = await repo.get_sender(ACCOUNT, dedicated.sender_id)
    assert after is not None
    assert after.cancelled is True


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("TX", False),
        ("TXT", True),
        ("TXTLOCAL123", True),
        ("TXTLOCAL1234", False),
        ("TXT LOCAL", False),
        ("TXT-LOCAL", False),
        ("TXT+LOCAL", True),
    ],
    ids=[
        "two-chars",
        "three-chars",
        "eleven-chars",
        "twelve-chars",
        "space-refused",
        "hyphen-refused",
        "plus-accepted",
    ],
)
def test_is_valid_alpha_tag(tag: str, expected: bool) -> None:
    assert is_valid_alpha_tag(tag) is expected


async def test_register_alpha_creates_an_under_review_sender(
    provisioned: SendersService, repo: InMemorySendersRepo
) -> None:
    tag = await provisioned.register_alpha(
        ACCOUNT, AlphaTagRequest(country="GB", tag=ALPHA_TAG, use_case=UseCase.MARKETING)
    )

    assert (tag.kind, tag.status, tag.country, tag.use_case, tag.value) == (
        SenderKind.ALPHA,
        SenderStatus.UNDER_REVIEW,
        "GB",
        UseCase.MARKETING,
        ALPHA_TAG,
    )
    assert tag.capabilities == (Channel.SMS,)
    assert await repo.get_sender(ACCOUNT, tag.sender_id) == tag


async def test_register_alpha_refuses_an_invalid_tag(provisioned: SendersService) -> None:
    with pytest.raises(BadRequest) as caught:
        await provisioned.register_alpha(
            ACCOUNT, AlphaTagRequest(country="GB", tag="AB", use_case=UseCase.MARKETING)
        )
    assert str(caught.value) == ALPHA_TAG_INVALID


async def test_register_alpha_refuses_a_country_without_a_shared_sender(
    provisioned: SendersService,
) -> None:
    with pytest.raises(BadRequest) as caught:
        await provisioned.register_alpha(
            ACCOUNT, AlphaTagRequest(country="US", tag=ALPHA_TAG, use_case=UseCase.MARKETING)
        )
    assert str(caught.value) == "Sending to US is not enabled for this account"


async def test_run_due_sweep_completes_every_alpha_tag_under_review(
    provisioned: SendersService, repo: InMemorySendersRepo
) -> None:
    first = await provisioned.register_alpha(
        ACCOUNT, AlphaTagRequest(country="GB", tag=ALPHA_TAG, use_case=UseCase.MARKETING)
    )
    second = await provisioned.register_alpha(
        ACCOUNT, AlphaTagRequest(country="GB", tag="OTHERCO", use_case=UseCase.OTHER)
    )

    swept = await provisioned.run_due_sweep(NOW)

    assert swept == 2
    for tag_id in (first.sender_id, second.sender_id):
        after = await repo.get_sender(ACCOUNT, tag_id)
        assert after is not None
        assert after.status is SenderStatus.READY


async def test_run_due_sweep_releases_a_cancelled_number_once_its_period_ends(
    provisioned: SendersService, repo: InMemorySendersRepo
) -> None:
    dedicated = await provisioned.buy_number(ACCOUNT, DEDICATED_NUMBER)
    await provisioned.remove(ACCOUNT, dedicated.sender_id)

    before_period_end = await provisioned.run_due_sweep(NOW)
    at_period_end = await provisioned.run_due_sweep(NOW + RENEWAL_PERIOD)

    assert before_period_end == 0
    assert at_period_end == 1
    after = await repo.get_sender(ACCOUNT, dedicated.sender_id)
    assert after is not None
    assert after.status is SenderStatus.RELEASED


async def test_due_for_renewal_excludes_a_cancelled_number(
    provisioned: SendersService,
) -> None:
    dedicated = await provisioned.buy_number(ACCOUNT, DEDICATED_NUMBER)
    await provisioned.remove(ACCOUNT, dedicated.sender_id)

    due = await provisioned.due_for_renewal(NOW + RENEWAL_PERIOD)

    assert due == []


async def test_search_numbers_delegates_to_the_catalogue(provisioned: SendersService) -> None:
    page = await provisioned.search_numbers(
        NumberSearchQuery(contains="", country="GB", page=1, use_for=UseFor.SMS)
    )

    assert page.page == 1
    assert len(page.numbers) == 13


async def test_buy_number_debits_the_account_and_creates_a_ready_dedicated_sender(
    provisioned: SendersService, repo: InMemorySendersRepo, billing: ScriptedBilling
) -> None:
    sender = await provisioned.buy_number(ACCOUNT, DEDICATED_NUMBER)

    assert (sender.kind, sender.status, sender.value, sender.country) == (
        SenderKind.DEDICATED,
        SenderStatus.READY,
        DEDICATED_NUMBER,
        "GB",
    )
    assert sender.monthly_price_micro == Micro(2_650_000)
    assert sender.renews_at == NOW + timedelta(days=30)
    assert await repo.get_sender(ACCOUNT, sender.sender_id) == sender
    assert billing.charged == [(ACCOUNT, sender.sender_id, Micro(2_650_000))]


async def test_buy_number_refuses_while_the_account_cannot_send(
    provisioned: SendersService, billing: ScriptedBilling
) -> None:
    billing.can_send = False

    with pytest.raises(BadRequest) as caught:
        await provisioned.buy_number(ACCOUNT, DEDICATED_NUMBER)
    assert str(caught.value) == TOP_UP_TO_RENT


async def test_buy_number_refuses_a_number_outside_the_catalogue(
    provisioned: SendersService,
) -> None:
    with pytest.raises(NotFound) as caught:
        await provisioned.buy_number(ACCOUNT, "+447000000000")
    assert str(caught.value) == NUMBER_NOT_FOUND


async def test_buy_number_propagates_a_declined_charge_and_creates_no_sender(
    provisioned: SendersService, repo: InMemorySendersRepo, billing: ScriptedBilling
) -> None:
    billing.charge_refused = True

    with pytest.raises(PaymentRequired):
        await provisioned.buy_number(ACCOUNT, DEDICATED_NUMBER)

    assert [
        sender for sender in await repo.list_senders(ACCOUNT) if sender.kind == "DEDICATED"
    ] == []

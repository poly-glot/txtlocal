from datetime import datetime, timedelta

import pytest

from txtlocal.shared.bus import Queue
from txtlocal.shared.errors import (
    INTERNAL_MESSAGE,
    BadRequest,
    Forbidden,
    Internal,
    NotFound,
    PaymentRequired,
)
from txtlocal.shared.money import Micro
from txtlocal.shared.testing import RecordingBus
from txtlocal.slices.billing.model import (
    DEFAULT_RECHARGE_AMOUNT_MICRO,
    Balance,
    CreateTopUpRequest,
    GeneralUpdate,
    LedgerKind,
    TopUpKind,
)
from txtlocal.slices.billing.repo import RECHARGE_IN_FLIGHT_TTL, TRIAL_SK
from txtlocal.slices.billing.service import (
    ACCOUNT_NOT_FOUND,
    INVALID_ALERT_THRESHOLD,
    INVALID_LOW_BALANCE_THRESHOLD,
    INVALID_RECHARGE_AMOUNT,
    LOW_BALANCE_ALERT_SUBJECT,
    RECHARGE_DECLINED_SUBJECT,
    TRIAL_ENDED,
    BillingService,
    low_balance_alert_body,
    recharge_declined_body,
)
from txtlocal.slices.billing.tests.fakes import (
    ACCOUNT_ID,
    CHECKOUT_URL,
    NOW,
    ZERO,
    FakeContact,
    FakeContacts,
    FakePaymentGateway,
    InMemoryBillingRepo,
    RecordingEmail,
    account_row,
    billing,
    ledger_of,
    uuid7_at,
)
from txtlocal.slices.messaging.model import Product

ONE_DAY = timedelta(days=1)
ONE_SECOND = timedelta(seconds=1)
TRIAL_ENDS_AT = NOW + 13 * ONE_DAY
TWO_POUNDS = Micro(2_000_000)
ONE_SMS = Micro(42_700)
CAMPAIGN_ID = uuid7_at(NOW - ONE_SECOND)
LATER = NOW + ONE_DAY
ONE_MS = timedelta(milliseconds=1)
RENEWS_AT = NOW - ONE_SECOND


def trial_repo(balance_micro: Micro = TWO_POUNDS) -> InMemoryBillingRepo:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=balance_micro, trial_ends_at=TRIAL_ENDS_AT)
    return repo


async def test_open_account_grants_two_pounds_for_fourteen_days() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo)

    await billing(repo).open_account(ACCOUNT_ID, NOW)

    account = repo.accounts[ACCOUNT_ID]
    assert (account.balance_micro, account.trial_ends_at) == (2_000_000, NOW + 14 * ONE_DAY)


async def test_open_account_writes_the_trial_row_under_its_fixed_key() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo)

    await billing(repo).open_account(ACCOUNT_ID, NOW)

    trial = repo.ledgers[ACCOUNT_ID][TRIAL_SK]
    assert (trial.kind, trial.amount_micro, trial.balance_after_micro, trial.ref) == (
        LedgerKind.TRIAL,
        2_000_000,
        2_000_000,
        None,
    )


async def test_open_account_twice_credits_once() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo)

    await billing(repo).open_account(ACCOUNT_ID, NOW)
    await billing(repo).open_account(ACCOUNT_ID, LATER)

    assert repo.accounts[ACCOUNT_ID].balance_micro == 2_000_000
    assert len(ledger_of(repo)) == 1


async def test_open_account_before_the_account_row_exists_is_lost() -> None:
    repo = InMemoryBillingRepo()

    await billing(repo).open_account(ACCOUNT_ID, NOW)

    assert repo.accounts == {}
    assert ledger_of(repo) == []


async def test_rate_reads_the_platform_rate() -> None:
    repo = InMemoryBillingRepo()
    repo.rates[("GB", Product.SMS)] = Micro(42_700)

    assert await billing(repo).rate("GB", Product.SMS) == 42_700


async def test_rate_missing_is_internal() -> None:
    with pytest.raises(Internal) as caught:
        await billing(InMemoryBillingRepo()).rate("GB", Product.MMS)
    assert caught.value.public_message() == INTERNAL_MESSAGE


async def test_balance_reads_the_account() -> None:
    balance = await billing(trial_repo(Micro(1_957_300))).balance(ACCOUNT_ID, NOW)

    assert balance == Balance(
        balance_micro=Micro(1_957_300),
        can_send=True,
        has_topped_up=False,
        trial_days_left=13,
        trial_ends_at=TRIAL_ENDS_AT,
    )


async def test_balance_of_a_missing_account_is_not_found() -> None:
    with pytest.raises(NotFound) as caught:
        await billing(InMemoryBillingRepo()).balance(ACCOUNT_ID, NOW)
    assert str(caught.value) == ACCOUNT_NOT_FOUND


async def test_reserve_covering_the_balance_exactly_succeeds() -> None:
    repo = trial_repo()

    await billing(repo).reserve(ACCOUNT_ID, TWO_POUNDS, CAMPAIGN_ID, NOW)

    assert repo.accounts[ACCOUNT_ID].balance_micro == 0


async def test_reserve_writes_the_send_row() -> None:
    repo = trial_repo()

    await billing(repo).reserve(ACCOUNT_ID, ONE_SMS, CAMPAIGN_ID, NOW)

    send = ledger_of(repo)[0]
    assert (send.kind, send.amount_micro, send.balance_after_micro, send.ref) == (
        LedgerKind.SEND,
        -42_700,
        1_957_300,
        CAMPAIGN_ID,
    )


async def test_reserve_one_micro_over_the_balance_is_refused() -> None:
    repo = trial_repo()

    with pytest.raises(PaymentRequired):
        await billing(repo).reserve(ACCOUNT_ID, Micro(2_000_001), CAMPAIGN_ID, NOW)

    assert repo.accounts[ACCOUNT_ID].balance_micro == 2_000_000
    assert ledger_of(repo) == []


async def test_refusal_names_the_balance_and_the_cost() -> None:
    repo = trial_repo(Micro(1_957_300))

    with pytest.raises(PaymentRequired) as caught:
        await billing(repo).reserve(ACCOUNT_ID, TWO_POUNDS, CAMPAIGN_ID, NOW)
    assert str(caught.value) == "Your balance is £1.9573; this send costs £2.00"


async def test_reserve_after_the_trial_ended_without_a_top_up_is_forbidden() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=TWO_POUNDS, trial_ends_at=NOW)

    with pytest.raises(Forbidden) as caught:
        await billing(repo).reserve(ACCOUNT_ID, ONE_SMS, CAMPAIGN_ID, NOW)
    assert str(caught.value) == TRIAL_ENDED
    assert repo.accounts[ACCOUNT_ID].balance_micro == 2_000_000


async def test_reserve_after_a_top_up_ignores_the_trial_end() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=TWO_POUNDS, has_topped_up=True, trial_ends_at=NOW - ONE_DAY)

    await billing(repo).reserve(ACCOUNT_ID, ONE_SMS, CAMPAIGN_ID, NOW)

    assert repo.accounts[ACCOUNT_ID].balance_micro == 1_957_300


async def test_reserve_of_one_micro_is_accepted() -> None:
    repo = trial_repo()

    await billing(repo).reserve(ACCOUNT_ID, Micro(1), CAMPAIGN_ID, NOW)

    assert repo.accounts[ACCOUNT_ID].balance_micro == 1_999_999


@pytest.mark.parametrize("amount_micro", [Micro(0), Micro(-1)], ids=["zero", "negative"])
async def test_reserve_of_nothing_is_internal(amount_micro: Micro) -> None:
    repo = trial_repo()

    with pytest.raises(Internal):
        await billing(repo).reserve(ACCOUNT_ID, amount_micro, CAMPAIGN_ID, NOW)

    assert repo.accounts[ACCOUNT_ID].balance_micro == 2_000_000


async def test_settle_credits_the_unspent_reservation() -> None:
    repo = trial_repo()
    service = billing(repo)
    await service.reserve(ACCOUNT_ID, TWO_POUNDS, CAMPAIGN_ID, NOW)

    await service.settle(ACCOUNT_ID, CAMPAIGN_ID, TWO_POUNDS, ONE_SMS, LATER)

    assert repo.accounts[ACCOUNT_ID].balance_micro == 1_957_300


async def test_settle_writes_the_refund_row() -> None:
    repo = trial_repo()
    service = billing(repo)
    await service.reserve(ACCOUNT_ID, TWO_POUNDS, CAMPAIGN_ID, NOW)

    await service.settle(ACCOUNT_ID, CAMPAIGN_ID, TWO_POUNDS, ONE_SMS, LATER)

    refund = ledger_of(repo)[1]
    assert (refund.kind, refund.amount_micro, refund.balance_after_micro, refund.ref) == (
        LedgerKind.REFUND,
        1_957_300,
        1_957_300,
        CAMPAIGN_ID,
    )


async def test_settle_twice_credits_once() -> None:
    repo = trial_repo()
    service = billing(repo)
    await service.reserve(ACCOUNT_ID, TWO_POUNDS, CAMPAIGN_ID, NOW)

    await service.settle(ACCOUNT_ID, CAMPAIGN_ID, TWO_POUNDS, ONE_SMS, LATER)
    await service.settle(ACCOUNT_ID, CAMPAIGN_ID, TWO_POUNDS, ONE_SMS, LATER + ONE_DAY)

    assert repo.accounts[ACCOUNT_ID].balance_micro == 1_957_300
    assert [row.kind for row in ledger_of(repo)] == [LedgerKind.SEND, LedgerKind.REFUND]


@pytest.mark.parametrize(
    ("reserved_micro", "settled_micro"),
    [(ONE_SMS, ONE_SMS), (ONE_SMS, Micro(50_000))],
    ids=["fully-spent", "overspent"],
)
async def test_settle_with_nothing_unspent_writes_nothing(
    reserved_micro: Micro, settled_micro: Micro
) -> None:
    repo = trial_repo()

    await billing(repo).settle(ACCOUNT_ID, CAMPAIGN_ID, reserved_micro, settled_micro, NOW)

    assert repo.accounts[ACCOUNT_ID].balance_micro == 2_000_000
    assert ledger_of(repo) == []


async def test_ledger_lists_newest_first() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo)
    service = billing(repo)
    await service.open_account(ACCOUNT_ID, NOW)
    await service.reserve(ACCOUNT_ID, ONE_SMS, uuid7_at(NOW), NOW + ONE_SECOND)
    await service.reserve(ACCOUNT_ID, ONE_SMS, uuid7_at(NOW), NOW + 2 * ONE_SECOND)

    page = await service.ledger(ACCOUNT_ID, None)

    assert [(row.kind, row.created_at) for row in page.items] == [
        (LedgerKind.SEND, NOW + 2 * ONE_SECOND),
        (LedgerKind.SEND, NOW + ONE_SECOND),
        (LedgerKind.TRIAL, NOW),
    ]


async def reserved(count: int) -> InMemoryBillingRepo:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=Micro(count), has_topped_up=True)
    service = billing(repo)
    for offset in range(count):
        await service.reserve(ACCOUNT_ID, Micro(1), CAMPAIGN_ID, NOW + offset * ONE_SECOND)
    return repo


@pytest.mark.parametrize(
    ("count", "first_page", "has_more"),
    [(19, 19, False), (20, 20, False), (21, 20, True)],
    ids=["under-a-page", "exactly-a-page", "one-over-a-page"],
)
async def test_ledger_page_size_ceiling(count: int, first_page: int, has_more: bool) -> None:
    page = await billing(await reserved(count)).ledger(ACCOUNT_ID, None)

    assert (len(page.items), page.next_cursor is not None) == (first_page, has_more)


async def test_ledger_cursor_continues_where_the_page_stopped() -> None:
    service = billing(await reserved(21))

    first = await service.ledger(ACCOUNT_ID, None)
    second = await service.ledger(ACCOUNT_ID, first.next_cursor)

    assert [row.created_at for row in second.items] == [NOW]
    assert second.next_cursor is None


def full_billing(
    repo: InMemoryBillingRepo,
    *,
    bus: RecordingBus | None = None,
    contacts: FakeContacts | None = None,
    email: RecordingEmail | None = None,
    gateway: FakePaymentGateway | None = None,
    now: datetime = NOW,
) -> BillingService:
    return BillingService(
        bus=RecordingBus() if bus is None else bus,
        clock=lambda: now,
        contacts=contacts,
        email=email,
        gateway=gateway,
        public_base_url="http://localhost:3000",
        repo=repo,
    )


def contacts_of(
    email: str = "a@b.example", mobile: str | None = None, name: str = "Acme"
) -> FakeContacts:
    return FakeContacts(FakeContact(email=email, mobile=mobile, name=name))


async def test_reserve_crossing_the_threshold_enqueues_one_recharge() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, auto_recharge=True, balance_micro=Micro(6_000_000), has_topped_up=True)
    bus = RecordingBus()

    await full_billing(repo, bus=bus).reserve(ACCOUNT_ID, Micro(2_000_000), CAMPAIGN_ID, NOW)

    assert repo.accounts[ACCOUNT_ID].balance_micro == 4_000_000
    assert [queue for queue, _ in bus.sent] == [Queue.RECHARGE]
    assert repo.accounts[ACCOUNT_ID].recharge_in_flight == NOW


async def test_reserve_while_a_recharge_is_already_in_flight_enqueues_nothing_more() -> None:
    repo = InMemoryBillingRepo()
    account_row(
        repo,
        auto_recharge=True,
        balance_micro=Micro(6_000_000),
        has_topped_up=True,
        recharge_in_flight=NOW - timedelta(hours=1),
    )
    bus = RecordingBus()

    await full_billing(repo, bus=bus).reserve(ACCOUNT_ID, Micro(2_000_000), CAMPAIGN_ID, NOW)

    assert bus.sent == []


async def test_reserve_without_crossing_the_threshold_enqueues_nothing() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, auto_recharge=True, balance_micro=Micro(10_000_000), has_topped_up=True)
    bus = RecordingBus()

    await full_billing(repo, bus=bus).reserve(ACCOUNT_ID, Micro(1_000_000), CAMPAIGN_ID, NOW)

    assert bus.sent == []


async def test_reserve_with_auto_recharge_off_enqueues_nothing() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, auto_recharge=False, balance_micro=Micro(6_000_000), has_topped_up=True)
    bus = RecordingBus()

    await full_billing(repo, bus=bus).reserve(ACCOUNT_ID, Micro(2_000_000), CAMPAIGN_ID, NOW)

    assert bus.sent == []


async def test_charge_rental_debits_the_monthly_price() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=Micro(3_000_000), has_topped_up=True)

    await billing(repo).charge_rental(ACCOUNT_ID, "sender-1", Micro(2_650_000), NOW, RENEWS_AT)

    assert repo.accounts[ACCOUNT_ID].balance_micro == 350_000
    rental = ledger_of(repo)[0]
    assert (rental.kind, rental.amount_micro, rental.ref) == (
        LedgerKind.RENTAL,
        -2_650_000,
        "sender-1",
    )


async def test_charge_rental_with_insufficient_balance_is_payment_required() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=Micro(1), has_topped_up=True)

    with pytest.raises(PaymentRequired):
        await billing(repo).charge_rental(ACCOUNT_ID, "sender-1", Micro(2_650_000), NOW, RENEWS_AT)

    assert repo.accounts[ACCOUNT_ID].balance_micro == 1


async def test_charge_rental_twice_for_the_same_period_debits_once() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=Micro(10_000_000), has_topped_up=True)
    service = billing(repo)

    await service.charge_rental(ACCOUNT_ID, "sender-1", Micro(2_650_000), NOW, RENEWS_AT)
    await service.charge_rental(ACCOUNT_ID, "sender-1", Micro(2_650_000), LATER, RENEWS_AT)

    assert repo.accounts[ACCOUNT_ID].balance_micro == 7_350_000
    assert [entry.kind for entry in ledger_of(repo)] == [LedgerKind.RENTAL]


async def test_charge_rental_for_the_next_period_debits_again() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=Micro(10_000_000), has_topped_up=True)
    service = billing(repo)

    await service.charge_rental(ACCOUNT_ID, "sender-1", Micro(2_650_000), NOW, RENEWS_AT)
    await service.charge_rental(
        ACCOUNT_ID, "sender-1", Micro(2_650_000), LATER, RENEWS_AT + ONE_DAY
    )

    assert repo.accounts[ACCOUNT_ID].balance_micro == 4_700_000


async def test_charge_rental_for_the_same_period_on_another_number_debits_again() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=Micro(10_000_000), has_topped_up=True)
    service = billing(repo)

    await service.charge_rental(ACCOUNT_ID, "sender-1", Micro(2_650_000), NOW, RENEWS_AT)
    await service.charge_rental(ACCOUNT_ID, "sender-2", Micro(2_650_000), LATER, RENEWS_AT)

    assert repo.accounts[ACCOUNT_ID].balance_micro == 4_700_000


@pytest.mark.parametrize(
    ("refusal", "expected"),
    [
        (INVALID_ALERT_THRESHOLD, "Choose a balance alert of £5.00, £10.00, £20.00 or £50.00"),
        (
            INVALID_LOW_BALANCE_THRESHOLD,
            "Choose a recharge threshold of £5.00, £10.00, £20.00 or £50.00",
        ),
        (INVALID_RECHARGE_AMOUNT, "Choose a recharge amount of £10.00, £30.00, £50.00 or £100.00"),
    ],
    ids=["alert-threshold", "recharge-threshold", "recharge-amount"],
)
def test_balance_management_refusals_name_every_choice(refusal: str, expected: str) -> None:
    assert refusal == expected


REFUSED_THRESHOLDS = [
    ZERO,
    Micro(4_999_999),
    Micro(5_000_001),
    Micro(15_000_000),
    Micro(50_000_001),
]
REFUSED_THRESHOLD_IDS = [
    "nothing",
    "a-micro-under-five-pounds",
    "a-micro-over-five-pounds",
    "between-choices",
    "a-micro-over-fifty-pounds",
]
ACCEPTED_THRESHOLDS = [Micro(5_000_000), Micro(10_000_000), Micro(20_000_000), Micro(50_000_000)]
ACCEPTED_THRESHOLD_IDS = ["five-pounds", "ten-pounds", "twenty-pounds", "fifty-pounds"]
LEGACY_MICRO = Micro(15_000_000)


@pytest.mark.parametrize(
    "amount_micro",
    [ZERO, Micro(9_999_999), Micro(10_000_001), Micro(20_000_000), Micro(100_000_001)],
    ids=[
        "nothing",
        "a-micro-under-the-smallest-boost",
        "a-micro-over-the-smallest-boost",
        "between-boosts",
        "a-micro-over-the-largest-boost",
    ],
)
async def test_update_general_refuses_a_recharge_amount_that_is_not_a_boost(
    amount_micro: Micro,
) -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True)
    service = full_billing(repo, contacts=contacts_of())

    with pytest.raises(BadRequest) as caught:
        await service.update_general(ACCOUNT_ID, GeneralUpdate(recharge_amount_micro=amount_micro))

    assert str(caught.value) == INVALID_RECHARGE_AMOUNT
    assert repo.accounts[ACCOUNT_ID].recharge_amount_micro == DEFAULT_RECHARGE_AMOUNT_MICRO


@pytest.mark.parametrize(
    "amount_micro",
    [Micro(10_000_000), Micro(30_000_000), Micro(50_000_000), Micro(100_000_000)],
    ids=["ten-pounds", "thirty-pounds", "fifty-pounds", "a-hundred-pounds"],
)
async def test_update_general_accepts_each_boost_as_the_recharge_amount(
    amount_micro: Micro,
) -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True)
    service = full_billing(repo, contacts=contacts_of())

    await service.update_general(ACCOUNT_ID, GeneralUpdate(recharge_amount_micro=amount_micro))

    assert repo.accounts[ACCOUNT_ID].recharge_amount_micro == amount_micro


async def test_update_general_keeps_a_legacy_recharge_amount() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True, recharge_amount_micro=LEGACY_MICRO)
    service = full_billing(repo, contacts=contacts_of())

    updated = await service.update_general(
        ACCOUNT_ID, GeneralUpdate(auto_recharge=True, recharge_amount_micro=LEGACY_MICRO)
    )

    assert updated.recharge_amount_micro == LEGACY_MICRO
    assert repo.accounts[ACCOUNT_ID].recharge_amount_micro == LEGACY_MICRO


@pytest.mark.parametrize("threshold_micro", REFUSED_THRESHOLDS, ids=REFUSED_THRESHOLD_IDS)
async def test_update_general_refuses_a_recharge_threshold_that_is_not_a_choice(
    threshold_micro: Micro,
) -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True)
    service = full_billing(repo, contacts=contacts_of())

    with pytest.raises(BadRequest) as caught:
        await service.update_general(
            ACCOUNT_ID, GeneralUpdate(low_balance_threshold_micro=threshold_micro)
        )

    assert str(caught.value) == INVALID_LOW_BALANCE_THRESHOLD


@pytest.mark.parametrize("threshold_micro", ACCEPTED_THRESHOLDS, ids=ACCEPTED_THRESHOLD_IDS)
async def test_update_general_accepts_each_recharge_threshold_choice(
    threshold_micro: Micro,
) -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True)
    service = full_billing(repo, contacts=contacts_of())

    await service.update_general(
        ACCOUNT_ID, GeneralUpdate(low_balance_threshold_micro=threshold_micro)
    )

    assert repo.accounts[ACCOUNT_ID].low_balance_threshold_micro == threshold_micro


@pytest.mark.parametrize("threshold_micro", REFUSED_THRESHOLDS, ids=REFUSED_THRESHOLD_IDS)
async def test_update_general_refuses_an_alert_threshold_that_is_not_a_choice(
    threshold_micro: Micro,
) -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True)
    service = full_billing(repo, contacts=contacts_of())

    with pytest.raises(BadRequest) as caught:
        await service.update_general(
            ACCOUNT_ID, GeneralUpdate(alert_threshold_micro=threshold_micro)
        )

    assert str(caught.value) == INVALID_ALERT_THRESHOLD


@pytest.mark.parametrize("threshold_micro", ACCEPTED_THRESHOLDS, ids=ACCEPTED_THRESHOLD_IDS)
async def test_update_general_accepts_each_alert_threshold_choice(
    threshold_micro: Micro,
) -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True)
    service = full_billing(repo, contacts=contacts_of())

    updated = await service.update_general(
        ACCOUNT_ID, GeneralUpdate(alert_threshold_micro=threshold_micro)
    )

    assert repo.accounts[ACCOUNT_ID].alert_threshold_micro == threshold_micro
    assert updated.alert_threshold_micro == threshold_micro


@pytest.mark.parametrize(
    "field",
    ["low_balance_threshold_micro", "alert_threshold_micro"],
    ids=["recharge-threshold", "alert-threshold"],
)
async def test_update_general_keeps_a_legacy_threshold(field: str) -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True, **{field: LEGACY_MICRO})
    service = full_billing(repo, contacts=contacts_of())

    updated = await service.update_general(
        ACCOUNT_ID, GeneralUpdate.model_validate({"auto_recharge": True, field: LEGACY_MICRO})
    )

    assert getattr(updated, field) == LEGACY_MICRO


async def test_packages_boosts_and_packs_use_the_countrys_rate() -> None:
    repo = InMemoryBillingRepo()
    repo.rates[("GB", Product.SMS)] = Micro(42_700)

    view = await billing(repo).packages("GB")

    assert view.rate_micro == 42_700
    assert [boost.estimate for boost in view.boosts] == [234, 702, 1_170, 2_341]
    assert [pack.estimate for pack in view.packs] == [7_751, 43_731, 127_795]
    assert [pack.savings_pct for pack in view.packs] == [9, 19, 26]


async def test_create_top_up_a_boost_creates_a_pending_row_and_a_checkout_url() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True)
    repo.rates[("GB", Product.SMS)] = Micro(42_700)
    gateway = FakePaymentGateway()
    service = full_billing(repo, contacts=contacts_of(), gateway=gateway)

    created = await service.create_top_up(
        ACCOUNT_ID, CreateTopUpRequest(code="BOOST_10", kind=TopUpKind.BOOST), NOW
    )

    assert created.checkout_url.startswith(CHECKOUT_URL)
    top_up = repo.topups[(ACCOUNT_ID, created.top_up_id)]
    assert (top_up.amount_micro, top_up.credited_micro) == (10_000_000, 10_000_000)
    assert repo.accounts[ACCOUNT_ID].stripe_customer_id is not None


async def test_create_top_up_a_pack_credits_the_boosted_amount() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True)
    repo.rates[("GB", Product.SMS)] = Micro(42_700)
    service = full_billing(
        repo,
        contacts=contacts_of(),
        gateway=FakePaymentGateway(),
    )

    created = await service.create_top_up(
        ACCOUNT_ID, CreateTopUpRequest(code="GROWTH", kind=TopUpKind.PACK), NOW
    )

    top_up = repo.topups[(ACCOUNT_ID, created.top_up_id)]
    assert top_up.credited_micro == 331_007_751


async def test_create_top_up_reuses_an_existing_stripe_customer() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True, stripe_customer_id="cus_existing")
    repo.rates[("GB", Product.SMS)] = Micro(42_700)
    gateway = FakePaymentGateway()
    service = full_billing(repo, contacts=contacts_of(), gateway=gateway)

    await service.create_top_up(
        ACCOUNT_ID, CreateTopUpRequest(code="BOOST_10", kind=TopUpKind.BOOST), NOW
    )

    assert repo.accounts[ACCOUNT_ID].stripe_customer_id == "cus_existing"
    assert gateway.customers == {}


async def test_create_top_up_with_an_unknown_code_is_bad_request() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True)
    repo.rates[("GB", Product.SMS)] = Micro(42_700)
    service = full_billing(
        repo,
        contacts=contacts_of(),
        gateway=FakePaymentGateway(),
    )

    with pytest.raises(BadRequest):
        await service.create_top_up(
            ACCOUNT_ID, CreateTopUpRequest(code="NOPE", kind=TopUpKind.BOOST), NOW
        )


async def test_create_top_up_without_a_gateway_configured_is_internal() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True)
    repo.rates[("GB", Product.SMS)] = Micro(42_700)
    service = full_billing(repo, contacts=contacts_of())

    with pytest.raises(Internal):
        await service.create_top_up(
            ACCOUNT_ID, CreateTopUpRequest(code="BOOST_10", kind=TopUpKind.BOOST), NOW
        )


async def test_cards_lists_the_seeded_visa_and_declining_card() -> None:
    gateway = FakePaymentGateway()
    customer_id = await gateway.ensure_customer(ACCOUNT_ID, "a@b.example")
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True, stripe_customer_id=customer_id)

    cards = await full_billing(repo, gateway=gateway).cards(ACCOUNT_ID)

    assert sorted(card.last4 for card in cards) == ["0002", "4242"]
    assert next(card for card in cards if card.last4 == "4242").is_default


async def test_cards_without_a_stripe_customer_is_empty() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True)

    assert await billing(repo).cards(ACCOUNT_ID) == []


async def test_general_combines_billing_fields_and_the_contact_reader() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, auto_recharge=True, has_topped_up=True)
    contacts = contacts_of(email="a@b.example", mobile="+447900000000", name="Acme")

    settings = await full_billing(repo, contacts=contacts).general(ACCOUNT_ID)

    assert (settings.auto_recharge, settings.email, settings.mobile, settings.name) == (
        True,
        "a@b.example",
        "+447900000000",
        "Acme",
    )


async def test_update_general_changes_only_the_balance_management_section() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True)
    contacts = contacts_of()
    service = full_billing(repo, contacts=contacts)

    updated = await service.update_general(
        ACCOUNT_ID, GeneralUpdate(auto_recharge=True, low_balance_threshold_micro=Micro(20_000_000))
    )

    assert (updated.auto_recharge, updated.low_balance_threshold_micro) == (True, 20_000_000)
    assert updated.name == "Acme"
    assert contacts.updates == []


async def test_update_general_changes_only_the_contact_section() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, has_topped_up=True)
    contacts = contacts_of(email="old@b.example", name="Old")
    service = full_billing(repo, contacts=contacts)

    updated = await service.update_general(
        ACCOUNT_ID, GeneralUpdate(email="new@b.example", name="New Name")
    )

    assert (updated.email, updated.name) == ("new@b.example", "New Name")
    assert contacts.updates == [(ACCOUNT_ID, "New Name", "new@b.example", None)]


async def test_credit_recharge_credits_the_balance_and_clears_the_flight_flag() -> None:
    repo = InMemoryBillingRepo()
    account_row(
        repo,
        balance_micro=Micro(1_000_000),
        has_topped_up=True,
        recharge_in_flight=NOW - timedelta(hours=1),
    )

    await billing(repo).credit_recharge(ACCOUNT_ID, Micro(10_000_000), "pi_1", NOW)

    account = repo.accounts[ACCOUNT_ID]
    assert (account.balance_micro, account.recharge_in_flight) == (11_000_000, None)


async def test_credit_recharge_is_idempotent_on_the_same_payment_intent() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=ZERO, has_topped_up=True)
    service = billing(repo)

    await service.credit_recharge(ACCOUNT_ID, Micro(10_000_000), "pi_1", NOW)
    await service.credit_recharge(ACCOUNT_ID, Micro(10_000_000), "pi_1", NOW + timedelta(hours=1))

    assert repo.accounts[ACCOUNT_ID].balance_micro == 10_000_000


async def test_abandon_recharge_clears_the_flight_flag() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, auto_recharge=True, has_topped_up=True, recharge_in_flight=NOW)

    await billing(repo).abandon_recharge(ACCOUNT_ID)

    assert repo.accounts[ACCOUNT_ID].recharge_in_flight is None


async def test_abandoned_recharge_lets_the_next_one_be_enqueued() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, auto_recharge=True, has_topped_up=True, recharge_in_flight=NOW)
    bus = RecordingBus()
    service = full_billing(repo, bus=bus)

    await service.abandon_recharge(ACCOUNT_ID)
    await service.request_recharge(ACCOUNT_ID, NOW)

    assert [queue for queue, _ in bus.sent] == [Queue.RECHARGE]


@pytest.mark.parametrize(
    ("in_flight_age", "expected"),
    [(RECHARGE_IN_FLIGHT_TTL, []), (RECHARGE_IN_FLIGHT_TTL + ONE_MS, [Queue.RECHARGE])],
    ids=["an-hour-old-flag-still-blocks", "a-millisecond-older-flag-is-stale"],
)
async def test_request_recharge_treats_an_old_flight_flag_as_stale(
    in_flight_age: timedelta, expected: list[Queue]
) -> None:
    repo = InMemoryBillingRepo()
    account_row(
        repo, auto_recharge=True, has_topped_up=True, recharge_in_flight=NOW - in_flight_age
    )
    bus = RecordingBus()

    await full_billing(repo, bus=bus).request_recharge(ACCOUNT_ID, NOW)

    assert [queue for queue, _ in bus.sent] == expected


async def test_decline_recharge_turns_off_auto_recharge_and_clears_the_flag() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, auto_recharge=True, has_topped_up=True, recharge_in_flight=NOW)

    await billing(repo).decline_recharge("recharge_x", ACCOUNT_ID, "insufficient_funds", NOW)

    account = repo.accounts[ACCOUNT_ID]
    assert (account.auto_recharge, account.recharge_in_flight) == (False, None)
    adjustment = ledger_of(repo)[0]
    assert (adjustment.kind, adjustment.amount_micro, adjustment.ref) == (
        LedgerKind.ADJUSTMENT,
        0,
        "insufficient_funds",
    )


async def test_request_recharge_enqueues_when_auto_recharge_is_on() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, auto_recharge=True, has_topped_up=True)
    bus = RecordingBus()

    await full_billing(repo, bus=bus).request_recharge(ACCOUNT_ID, NOW)

    assert [queue for queue, _ in bus.sent] == [Queue.RECHARGE]


async def test_request_recharge_does_nothing_when_auto_recharge_is_off() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, auto_recharge=False, has_topped_up=True)
    bus = RecordingBus()

    await full_billing(repo, bus=bus).request_recharge(ACCOUNT_ID, NOW)

    assert bus.sent == []


@pytest.mark.parametrize(
    ("balance_micro", "amount_micro", "expect_alert"),
    [
        (Micro(6_000_000), Micro(2_000_000), True),
        (Micro(5_000_000), Micro(1), True),
        (Micro(4_999_999), Micro(1), False),
        (Micro(10_000_000), Micro(1_000_000), False),
    ],
    ids=[
        "crosses-from-above",
        "crosses-from-exactly-at-threshold",
        "already-below-does-not-alert",
        "stays-above-no-alert",
    ],
)
async def test_reserve_alerts_on_low_balance_crossing_only(
    balance_micro: Micro, amount_micro: Micro, expect_alert: bool
) -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=balance_micro, has_topped_up=True)
    email = RecordingEmail()

    await full_billing(repo, contacts=contacts_of(), email=email).reserve(
        ACCOUNT_ID, amount_micro, CAMPAIGN_ID, NOW
    )

    assert bool(email.sent) is expect_alert
    if expect_alert:
        assert repo.accounts[ACCOUNT_ID].low_balance_alerted_at == NOW
        assert email.sent == [
            ("a@b.example", LOW_BALANCE_ALERT_SUBJECT, low_balance_alert_body(Micro(5_000_000)))
        ]
    else:
        assert repo.accounts[ACCOUNT_ID].low_balance_alerted_at is None


async def test_reserve_alerts_at_the_alert_threshold_not_the_recharge_threshold() -> None:
    repo = InMemoryBillingRepo()
    account_row(
        repo,
        alert_threshold_micro=Micro(20_000_000),
        balance_micro=Micro(21_000_000),
        has_topped_up=True,
        low_balance_threshold_micro=Micro(5_000_000),
    )
    email = RecordingEmail()

    await full_billing(repo, contacts=contacts_of(), email=email).reserve(
        ACCOUNT_ID, Micro(2_000_000), CAMPAIGN_ID, NOW
    )

    assert email.sent == [
        ("a@b.example", LOW_BALANCE_ALERT_SUBJECT, low_balance_alert_body(Micro(20_000_000)))
    ]


async def test_reserve_crossing_only_the_recharge_threshold_sends_no_alert() -> None:
    repo = InMemoryBillingRepo()
    account_row(
        repo,
        alert_threshold_micro=Micro(5_000_000),
        balance_micro=Micro(21_000_000),
        has_topped_up=True,
        low_balance_threshold_micro=Micro(20_000_000),
    )
    email = RecordingEmail()

    await full_billing(repo, contacts=contacts_of(), email=email).reserve(
        ACCOUNT_ID, Micro(2_000_000), CAMPAIGN_ID, NOW
    )

    assert email.sent == []


async def test_reserve_low_balance_alert_fires_once_across_repeated_debits() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=Micro(6_000_000), has_topped_up=True)
    email = RecordingEmail()
    service = full_billing(repo, contacts=contacts_of(), email=email)

    await service.reserve(ACCOUNT_ID, Micro(2_000_000), CAMPAIGN_ID, NOW)
    await service.reserve(ACCOUNT_ID, Micro(1_000_000), CAMPAIGN_ID, NOW + ONE_SECOND)

    assert len(email.sent) == 1


async def test_reserve_does_not_alert_without_email_or_contacts_configured() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=Micro(6_000_000), has_topped_up=True)

    await full_billing(repo).reserve(ACCOUNT_ID, Micro(2_000_000), CAMPAIGN_ID, NOW)

    assert repo.accounts[ACCOUNT_ID].low_balance_alerted_at is None


async def test_credit_recharge_above_the_threshold_clears_the_low_balance_alert() -> None:
    repo = InMemoryBillingRepo()
    account_row(
        repo, balance_micro=Micro(4_000_000), has_topped_up=True, low_balance_alerted_at=NOW
    )

    await billing(repo).credit_recharge(ACCOUNT_ID, Micro(10_000_000), "pi_1", NOW)

    assert repo.accounts[ACCOUNT_ID].low_balance_alerted_at is None


async def test_credit_recharge_still_below_the_threshold_keeps_the_alert() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=Micro(1), has_topped_up=True, low_balance_alerted_at=NOW)

    await billing(repo).credit_recharge(ACCOUNT_ID, Micro(1_000_000), "pi_1", NOW)

    assert repo.accounts[ACCOUNT_ID].low_balance_alerted_at == NOW


async def test_decline_recharge_sends_one_alert_email() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, auto_recharge=True, has_topped_up=True, recharge_in_flight=NOW)
    email = RecordingEmail()

    await full_billing(repo, contacts=contacts_of(), email=email).decline_recharge(
        "recharge_x", ACCOUNT_ID, "insufficient_funds", NOW
    )

    assert email.sent == [
        (
            "a@b.example",
            RECHARGE_DECLINED_SUBJECT,
            recharge_declined_body("insufficient_funds"),
        )
    ]


async def test_decline_recharge_redelivered_does_not_resend_the_alert() -> None:
    repo = InMemoryBillingRepo()
    account_row(repo, auto_recharge=True, has_topped_up=True, recharge_in_flight=NOW)
    email = RecordingEmail()
    service = full_billing(repo, contacts=contacts_of(), email=email)

    await service.decline_recharge("recharge_x", ACCOUNT_ID, "insufficient_funds", NOW)
    await service.decline_recharge("recharge_x", ACCOUNT_ID, "insufficient_funds", NOW + ONE_SECOND)

    assert len(email.sent) == 1

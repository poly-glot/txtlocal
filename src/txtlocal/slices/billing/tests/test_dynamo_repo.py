from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from txtlocal.shared.errors import PaymentRequired
from txtlocal.shared.money import Micro
from txtlocal.shared.table import Table, key, n
from txtlocal.shared.testing import local_repo_table
from txtlocal.slices.billing.gateway import PaymentEvent
from txtlocal.slices.billing.model import LedgerKind, LedgerOrder, TopUp, TopUpKind, TopUpStatus
from txtlocal.slices.billing.repo import (
    PLATFORM,
    RECHARGE_IN_FLIGHT_TTL,
    BillingDynamoRepo,
    account_key,
    rate_sort_key,
)
from txtlocal.slices.billing.service import BillingService, ledger_entry
from txtlocal.slices.billing.tests.fakes import ACCOUNT_ID, NOW, ZERO, uuid7_at
from txtlocal.slices.messaging.model import Product

if TYPE_CHECKING:
    from types_aiobotocore_dynamodb.type_defs import AttributeValueTypeDef

ONE_DAY = timedelta(days=1)
ONE_MS = timedelta(milliseconds=1)
ONE_SECOND = timedelta(seconds=1)
RENEWS_AT = NOW - ONE_SECOND
SENDER_ID = "sender-1"
TWO_POUNDS = Micro(2_000_000)
ONE_SMS = Micro(42_700)
CAMPAIGN_ID = uuid7_at(NOW - ONE_SECOND)


async def seed_account(
    table: Table, balance_micro: Micro = ZERO, *, has_topped_up: bool = False
) -> BillingService:
    item: dict[str, AttributeValueTypeDef] = {
        **account_key(ACCOUNT_ID),
        "balanceMicro": n(balance_micro),
        "hasToppedUp": {"BOOL": has_topped_up},
    }
    await table.client.put_item(Item=item, TableName=table.name)
    return BillingService(clock=lambda: NOW, repo=BillingDynamoRepo(table))


async def opened(table: Table) -> BillingService:
    service = await seed_account(table)
    await service.open_account(ACCOUNT_ID, NOW)
    return service


async def test_open_account_grants_the_trial_in_one_transaction() -> None:
    async with local_repo_table("billing") as table:
        service = await opened(table)

        balance = await service.balance(ACCOUNT_ID, NOW)
        page = await service.ledger(ACCOUNT_ID, None)

        assert (balance.balance_micro, balance.trial_ends_at) == (2_000_000, NOW + 14 * ONE_DAY)
        assert [(row.kind, row.amount_micro) for row in page.items] == [
            (LedgerKind.TRIAL, 2_000_000)
        ]


async def test_open_account_twice_loses_the_condition_without_an_error() -> None:
    async with local_repo_table("billing") as table:
        service = await opened(table)

        await service.open_account(ACCOUNT_ID, NOW + ONE_DAY)

        balance = await service.balance(ACCOUNT_ID, NOW)
        assert (balance.balance_micro, balance.trial_ends_at) == (2_000_000, NOW + 14 * ONE_DAY)


async def test_open_account_before_the_account_row_creates_nothing() -> None:
    async with local_repo_table("billing") as table:
        repo = BillingDynamoRepo(table)
        service = BillingService(clock=lambda: NOW, repo=repo)

        await service.open_account(ACCOUNT_ID, NOW)

        assert await repo.load_account(ACCOUNT_ID) is None
        assert (await repo.ledger_page(ACCOUNT_ID, None)).items == []


async def test_reserve_covering_the_balance_exactly_debits_it() -> None:
    async with local_repo_table("billing") as table:
        service = await opened(table)

        await service.reserve(ACCOUNT_ID, TWO_POUNDS, CAMPAIGN_ID, NOW)

        balance = await service.balance(ACCOUNT_ID, NOW)
        assert balance.balance_micro == 0


async def test_reserve_one_micro_over_the_balance_loses_the_covering_condition() -> None:
    async with local_repo_table("billing") as table:
        service = await opened(table)

        with pytest.raises(PaymentRequired) as caught:
            await service.reserve(ACCOUNT_ID, Micro(2_000_001), CAMPAIGN_ID, NOW)

        assert str(caught.value) == "Your balance is £2.00; this send costs £2.00"
        assert (await service.balance(ACCOUNT_ID, NOW)).balance_micro == 2_000_000
        assert [row.kind for row in (await service.ledger(ACCOUNT_ID, None)).items] == [
            LedgerKind.TRIAL
        ]


async def test_settle_credits_the_unspent_reservation_once() -> None:
    async with local_repo_table("billing") as table:
        service = await opened(table)
        await service.reserve(ACCOUNT_ID, TWO_POUNDS, CAMPAIGN_ID, NOW)

        await service.settle(ACCOUNT_ID, CAMPAIGN_ID, TWO_POUNDS, ONE_SMS, NOW + ONE_DAY)
        await service.settle(ACCOUNT_ID, CAMPAIGN_ID, TWO_POUNDS, ONE_SMS, NOW + 2 * ONE_DAY)

        balance = await service.balance(ACCOUNT_ID, NOW)
        page = await service.ledger(ACCOUNT_ID, None)
        assert balance.balance_micro == 1_957_300
        assert [(row.kind, row.amount_micro, row.balance_after_micro) for row in page.items] == [
            (LedgerKind.SEND, -2_000_000, 0),
            (LedgerKind.REFUND, 1_957_300, 1_957_300),
            (LedgerKind.TRIAL, 2_000_000, 2_000_000),
        ]


@pytest.mark.parametrize(
    ("count", "first_page", "has_more"),
    [(20, 20, False), (21, 20, True)],
    ids=["exactly-a-page", "one-over-a-page"],
)
async def test_ledger_pages_newest_first_and_continues_from_the_cursor(
    count: int, first_page: int, has_more: bool
) -> None:
    async with local_repo_table("billing") as table:
        service = await seed_account(table, Micro(count), has_topped_up=True)
        for offset in range(count):
            await service.reserve(ACCOUNT_ID, Micro(1), CAMPAIGN_ID, NOW + offset * ONE_SECOND)

        first = await service.ledger(ACCOUNT_ID, None)

        assert (len(first.items), first.next_cursor is not None) == (first_page, has_more)
        assert first.items[0].created_at == NOW + (count - 1) * ONE_SECOND
        if first.next_cursor is not None:
            second = await service.ledger(ACCOUNT_ID, first.next_cursor)
            assert ([row.created_at for row in second.items], second.next_cursor) == ([NOW], None)


@pytest.mark.parametrize(
    ("product", "expected"),
    [(Product.SMS, Micro(42_700)), (Product.MMS, None)],
    ids=["seeded-rate", "missing-rate"],
)
async def test_rate_reads_the_platform_row(product: Product, expected: Micro | None) -> None:
    async with local_repo_table("billing") as table:
        await table.client.put_item(
            Item={**key(PLATFORM, rate_sort_key("GB", Product.SMS)), "priceMicro": n(42_700)},
            TableName=table.name,
        )

        assert await BillingDynamoRepo(table).rate("GB", product) == expected


async def test_credit_top_up_redelivered_event_credits_the_balance_once() -> None:
    async with local_repo_table("billing") as table:
        service = await seed_account(table)
        top_up_id = uuid7_at(NOW)
        await service.repo.put_topup(
            TopUp(
                account_id=ACCOUNT_ID,
                amount_micro=Micro(10_000_000),
                code="BOOST_10",
                created_at=NOW,
                credited_micro=Micro(10_000_000),
                kind=TopUpKind.BOOST,
                status=TopUpStatus.PENDING,
                top_up_id=top_up_id,
            )
        )
        event = PaymentEvent(
            event_id="evt_redelivered",
            event_type="checkout.session.completed",
            account_id=ACCOUNT_ID,
            invoice_number="INV-1",
            invoice_url="https://stripe.example/invoice/1",
            top_up_id=top_up_id,
        )

        await service.credit_top_up(event, NOW)
        await service.credit_top_up(event, NOW + ONE_SECOND)

        balance = await service.balance(ACCOUNT_ID, NOW)
        page = await service.ledger(ACCOUNT_ID, None)
        paid = await service.repo.get_topup(ACCOUNT_ID, top_up_id)

        assert (balance.balance_micro, balance.has_topped_up) == (10_000_000, True)
        assert [(row.kind, row.amount_micro, row.stripe_invoice_number) for row in page.items] == [
            (LedgerKind.TOPUP, 10_000_000, "INV-1")
        ]
        assert paid is not None
        assert paid.status is TopUpStatus.PAID


async def test_set_then_clear_low_balance_alert_round_trips() -> None:
    async with local_repo_table("billing") as table:
        service = await seed_account(table, Micro(1), has_topped_up=True)
        repo = service.repo

        first_set = await repo.set_low_balance_alerted(ACCOUNT_ID, NOW)
        second_set = await repo.set_low_balance_alerted(ACCOUNT_ID, NOW + ONE_SECOND)
        alerted = await repo.load_account(ACCOUNT_ID)

        first_clear = await repo.clear_low_balance_alert(ACCOUNT_ID)
        second_clear = await repo.clear_low_balance_alert(ACCOUNT_ID)
        cleared = await repo.load_account(ACCOUNT_ID)

        assert (first_set, second_set) == (True, False)
        assert alerted is not None
        assert alerted.low_balance_alerted_at == NOW
        assert (first_clear, second_clear) == (True, False)
        assert cleared is not None
        assert cleared.low_balance_alerted_at is None


async def test_topups_page_lists_only_topup_kind_entries() -> None:
    async with local_repo_table("billing") as table:
        service = await seed_account(table, Micro(1), has_topped_up=True)
        await service.reserve(ACCOUNT_ID, Micro(1), CAMPAIGN_ID, NOW)
        top_up_id = uuid7_at(NOW + ONE_SECOND)
        await service.repo.put_topup(
            TopUp(
                account_id=ACCOUNT_ID,
                amount_micro=Micro(10_000_000),
                code="BOOST_10",
                created_at=NOW + ONE_SECOND,
                credited_micro=Micro(10_000_000),
                kind=TopUpKind.BOOST,
                status=TopUpStatus.PENDING,
                top_up_id=top_up_id,
            )
        )
        await service.credit_top_up(
            PaymentEvent(
                event_id="evt_1",
                event_type="checkout.session.completed",
                account_id=ACCOUNT_ID,
                top_up_id=top_up_id,
            ),
            NOW + ONE_SECOND,
        )

        page = await service.transactions(ACCOUNT_ID, None, LedgerOrder.DESC)

        assert [row.kind for row in page.items] == [LedgerKind.TOPUP]


async def test_charge_rental_twice_for_the_same_period_debits_once() -> None:
    async with local_repo_table("billing") as table:
        service = await seed_account(table, Micro(10_000_000), has_topped_up=True)

        await service.charge_rental(ACCOUNT_ID, SENDER_ID, Micro(2_650_000), NOW, RENEWS_AT)
        await service.charge_rental(
            ACCOUNT_ID, SENDER_ID, Micro(2_650_000), NOW + ONE_DAY, RENEWS_AT
        )

        balance = await service.balance(ACCOUNT_ID, NOW)
        page = await service.ledger(ACCOUNT_ID, None)

        assert balance.balance_micro == 7_350_000
        assert [row.kind for row in page.items] == [LedgerKind.RENTAL]


async def test_charge_rental_for_the_next_period_debits_again() -> None:
    async with local_repo_table("billing") as table:
        service = await seed_account(table, Micro(10_000_000), has_topped_up=True)

        await service.charge_rental(ACCOUNT_ID, SENDER_ID, Micro(2_650_000), NOW, RENEWS_AT)
        await service.charge_rental(
            ACCOUNT_ID, SENDER_ID, Micro(2_650_000), NOW + ONE_DAY, RENEWS_AT + ONE_DAY
        )

        balance = await service.balance(ACCOUNT_ID, NOW)
        assert balance.balance_micro == 4_700_000


async def test_charge_rental_one_micro_over_the_balance_is_payment_required() -> None:
    async with local_repo_table("billing") as table:
        service = await seed_account(table, Micro(2_649_999), has_topped_up=True)

        with pytest.raises(PaymentRequired):
            await service.charge_rental(ACCOUNT_ID, SENDER_ID, Micro(2_650_000), NOW, RENEWS_AT)

        balance = await service.balance(ACCOUNT_ID, NOW)
        assert balance.balance_micro == 2_649_999


@pytest.mark.parametrize(
    ("in_flight_age", "expected"),
    [(RECHARGE_IN_FLIGHT_TTL, False), (RECHARGE_IN_FLIGHT_TTL + ONE_MS, True)],
    ids=["an-hour-old-flag-still-blocks", "a-millisecond-older-flag-is-stale"],
)
async def test_set_recharge_in_flight_treats_an_old_flag_as_stale(
    in_flight_age: timedelta, expected: bool
) -> None:
    async with local_repo_table("billing") as table:
        repo = BillingDynamoRepo(table)
        await seed_account(table)
        await repo.set_recharge_in_flight(ACCOUNT_ID, NOW - in_flight_age)

        assert await repo.set_recharge_in_flight(ACCOUNT_ID, NOW) is expected


async def test_clear_recharge_in_flight_lets_the_next_one_claim_the_flag() -> None:
    async with local_repo_table("billing") as table:
        repo = BillingDynamoRepo(table)
        await seed_account(table)
        await repo.set_recharge_in_flight(ACCOUNT_ID, NOW)

        cleared = await repo.clear_recharge_in_flight(ACCOUNT_ID)
        claimed_again = await repo.set_recharge_in_flight(ACCOUNT_ID, NOW)

        assert (cleared, claimed_again) == (True, True)


async def test_clear_recharge_in_flight_without_a_flag_loses_the_condition() -> None:
    async with local_repo_table("billing") as table:
        repo = BillingDynamoRepo(table)
        await seed_account(table)

        assert await repo.clear_recharge_in_flight(ACCOUNT_ID) is False


async def test_credit_recharge_redelivered_payment_intent_credits_once() -> None:
    async with local_repo_table("billing") as table:
        service = await seed_account(table, has_topped_up=True)

        await service.credit_recharge(ACCOUNT_ID, Micro(10_000_000), "pi_1", NOW)
        await service.credit_recharge(ACCOUNT_ID, Micro(10_000_000), "pi_1", NOW + ONE_SECOND)

        balance = await service.balance(ACCOUNT_ID, NOW)
        assert balance.balance_micro == 10_000_000


async def credited_top_ups(table: Table, count: int) -> BillingService:
    service = await seed_account(table, has_topped_up=True)
    for offset in range(count):
        entry = ledger_entry(
            LedgerKind.TOPUP, Micro(1), Micro(offset + 1), NOW + offset * ONE_SECOND
        )
        await service.repo.credit(ACCOUNT_ID, entry)
    return service


@pytest.mark.parametrize(
    ("order", "first_offset"),
    [(LedgerOrder.ASC, 0), (LedgerOrder.DESC, 20)],
    ids=["oldest-first", "newest-first"],
)
async def test_topups_page_reads_in_the_requested_order(
    order: LedgerOrder, first_offset: int
) -> None:
    async with local_repo_table("billing") as table:
        service = await credited_top_ups(table, 21)

        page = await service.transactions(ACCOUNT_ID, None, order)

        assert page.items[0].created_at == NOW + first_offset * ONE_SECOND


async def test_topups_page_oldest_first_continues_from_the_cursor() -> None:
    async with local_repo_table("billing") as table:
        service = await credited_top_ups(table, 21)

        first = await service.transactions(ACCOUNT_ID, None, LedgerOrder.ASC)
        second = await service.transactions(ACCOUNT_ID, first.next_cursor, LedgerOrder.ASC)

        assert len(first.items) == 20
        assert [row.created_at for row in second.items] == [NOW + 20 * ONE_SECOND]

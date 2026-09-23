from datetime import timedelta

import pytest

from txtlocal.shared.money import Micro
from txtlocal.shared.testing import local_repo_table
from txtlocal.slices.senders.model import SHARED_VALUE, SenderKind, SenderStatus, SmartSender
from txtlocal.slices.senders.repo import SendersDynamoRepo, SendersRepo
from txtlocal.slices.senders.tests.fakes import ACCOUNT, ALPHA_TAG, NOW, OWN_NUMBER, sender_of

SHARED = sender_of(
    SenderKind.SHARED, SHARED_VALUE, provider_identity="shared-pool", sender_id="shared-1"
)
SMART = SmartSender(country="GB", sender_id=SHARED.sender_id)
OWN = sender_of(
    SenderKind.OWN,
    OWN_NUMBER,
    nickname="Sam's Phone",
    sender_id="own-1",
    status=SenderStatus.PENDING_VERIFICATION,
)
OWN_SMART = SmartSender(country="GB", sender_id=OWN.sender_id)
DEDICATED = sender_of(SenderKind.DEDICATED, "+447700900123", sender_id="dedicated-1").model_copy(
    update={"monthly_price_micro": Micro(2_000_000), "renews_at": NOW}
)
ALPHA = sender_of(
    SenderKind.ALPHA, ALPHA_TAG, sender_id="alpha-1", status=SenderStatus.UNDER_REVIEW
)


async def test_defaults_round_trip_through_the_table() -> None:
    async with local_repo_table("senders") as table:
        repo: SendersRepo = SendersDynamoRepo(table)
        await repo.put_defaults_if_absent(ACCOUNT, SHARED, SMART)

        listed = (await repo.list_senders(ACCOUNT), await repo.list_smart(ACCOUNT))

        assert listed == ([SHARED], [SMART])


async def test_defaults_second_put_loses_and_writes_nothing() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)
        first = await repo.put_defaults_if_absent(ACCOUNT, SHARED, SMART)

        second = await repo.put_defaults_if_absent(
            ACCOUNT, SHARED.model_copy(update={"sender_id": "shared-2"}), SMART
        )

        assert (first, second) == (True, False)
        assert await repo.list_senders(ACCOUNT) == [SHARED]


async def test_get_sender_is_none_for_a_missing_row() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)

        assert await repo.get_sender(ACCOUNT, "missing") is None


async def test_own_number_round_trips_with_its_optional_fields() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)
        await repo.put_sender(ACCOUNT, OWN)

        assert await repo.get_sender(ACCOUNT, OWN.sender_id) == OWN


async def test_mark_verified_sets_status_and_verified_at() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)
        await repo.put_sender(ACCOUNT, OWN)

        marked = await repo.mark_verified(ACCOUNT, OWN.sender_id, NOW)

        assert marked is True
        assert await repo.get_sender(ACCOUNT, OWN.sender_id) == OWN.model_copy(
            update={"status": SenderStatus.READY, "verified_at": NOW}
        )


async def test_mark_verified_is_false_for_a_missing_row() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)

        assert await repo.mark_verified(ACCOUNT, "missing", NOW) is False


async def test_delete_sender_wins_once() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)
        await repo.put_sender(ACCOUNT, OWN)

        outcomes = (
            await repo.delete_sender(ACCOUNT, OWN.sender_id),
            await repo.delete_sender(ACCOUNT, OWN.sender_id),
        )

        assert outcomes == (True, False)


@pytest.mark.parametrize(
    ("current", "expected"),
    [(OWN.sender_id, True), (SHARED.sender_id, False)],
    ids=["pointing-at-it-replaces", "pointing-elsewhere-leaves-it"],
)
async def test_replace_smart_if_pointing_at(current: str, expected: bool) -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)
        await repo.set_smart(ACCOUNT, OWN_SMART)

        replaced = await repo.replace_smart_if_pointing_at(ACCOUNT, SMART, current)

        assert replaced is expected
        assert await repo.list_smart(ACCOUNT) == [SMART if expected else OWN_SMART]


async def test_rented_numbers_finds_active_rentals_across_accounts() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)
        await repo.put_sender(ACCOUNT, DEDICATED)
        await repo.put_sender(
            "account-2", DEDICATED.model_copy(update={"sender_id": "dedicated-2"})
        )
        await repo.put_sender(ACCOUNT, OWN)

        rented = await repo.rented_numbers()

        assert {(account_id, sender.sender_id) for account_id, sender in rented} == {
            (ACCOUNT, "dedicated-1"),
            ("account-2", "dedicated-2"),
        }


async def test_record_renewal_advances_renews_at_and_resets_attempts() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)
        due = DEDICATED.model_copy(update={"renewal_attempt": 3})
        await repo.put_sender(ACCOUNT, due)

        renewed_at = NOW + timedelta(days=30)
        outcome = await repo.record_renewal(ACCOUNT, due.sender_id, renewed_at)

        assert outcome is True
        assert await repo.get_sender(ACCOUNT, due.sender_id) == due.model_copy(
            update={"renewal_attempt": 0, "renews_at": renewed_at}
        )


async def test_record_renewal_is_false_for_a_missing_row() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)

        assert await repo.record_renewal(ACCOUNT, "missing", NOW) is False


async def test_record_renewal_attempt_increments_atomically() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)
        await repo.put_sender(ACCOUNT, DEDICATED)

        await repo.record_renewal_attempt(ACCOUNT, DEDICATED.sender_id)
        await repo.record_renewal_attempt(ACCOUNT, DEDICATED.sender_id)

        twice = await repo.get_sender(ACCOUNT, DEDICATED.sender_id)
        assert twice is not None
        assert twice.renewal_attempt == 2


async def test_record_renewal_attempt_is_false_for_a_missing_row() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)

        assert await repo.record_renewal_attempt(ACCOUNT, "missing") is False


async def test_release_sets_status_and_drops_out_of_the_rented_sweep() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)
        await repo.put_sender(ACCOUNT, DEDICATED)

        released = await repo.release(ACCOUNT, DEDICATED.sender_id)

        assert released is True
        assert await repo.rented_numbers() == []

        after = await repo.get_sender(ACCOUNT, DEDICATED.sender_id)
        assert after is not None
        assert after.status is SenderStatus.RELEASED


async def test_release_is_false_for_a_missing_row() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)

        assert await repo.release(ACCOUNT, "missing") is False


async def test_cancel_rental_sets_the_flag_and_leaves_status_untouched() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)
        await repo.put_sender(ACCOUNT, DEDICATED)

        cancelled = await repo.cancel_rental(ACCOUNT, DEDICATED.sender_id)

        assert cancelled is True
        after = await repo.get_sender(ACCOUNT, DEDICATED.sender_id)
        assert after is not None
        assert (after.cancelled, after.status) == (True, SenderStatus.READY)
        assert await repo.rented_numbers() == [(ACCOUNT, after)]


async def test_cancel_rental_is_false_for_a_missing_row() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)

        assert await repo.cancel_rental(ACCOUNT, "missing") is False


async def test_alpha_tags_under_review_finds_rows_across_accounts() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)
        await repo.put_sender(ACCOUNT, ALPHA)
        await repo.put_sender(
            "account-2", ALPHA.model_copy(update={"sender_id": "alpha-2", "value": "OTHERCO"})
        )
        await repo.put_sender(ACCOUNT, OWN)

        under_review = await repo.alpha_tags_under_review()

        assert {(account_id, sender.sender_id) for account_id, sender in under_review} == {
            (ACCOUNT, "alpha-1"),
            ("account-2", "alpha-2"),
        }


@pytest.mark.parametrize(
    "status",
    [SenderStatus.READY, SenderStatus.REJECTED],
    ids=["approved", "rejected"],
)
async def test_complete_alpha_tag_sets_status_and_drops_out_of_the_review_sweep(
    status: SenderStatus,
) -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)
        await repo.put_sender(ACCOUNT, ALPHA)

        completed = await repo.complete_alpha_tag(ACCOUNT, ALPHA.sender_id, status)

        assert completed is True
        assert await repo.alpha_tags_under_review() == []

        after = await repo.get_sender(ACCOUNT, ALPHA.sender_id)
        assert after is not None
        assert after.status is status


async def test_complete_alpha_tag_is_false_for_a_missing_row() -> None:
    async with local_repo_table("senders") as table:
        repo = SendersDynamoRepo(table)

        assert await repo.complete_alpha_tag(ACCOUNT, "missing", SenderStatus.READY) is False

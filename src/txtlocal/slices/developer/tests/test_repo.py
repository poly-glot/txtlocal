from datetime import UTC, datetime

from txtlocal.shared.testing import local_repo_table
from txtlocal.slices.developer.model import IdempotencyStatus
from txtlocal.slices.developer.repo import DeveloperDynamoRepo

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=UTC)
ACCOUNT_ID = "acc_dev_repo"
USER_ID = "usr_dev_repo"
CAMPAIGN_ID = "cmp_first"
OTHER_CAMPAIGN_ID = "cmp_second"
IDEMPOTENCY_KEY = "order-8812"
MESSAGE_ID = "msg_dev_repo_1"
OTHER_MESSAGE_ID = "msg_dev_repo_2"
UNWRITTEN_MESSAGE_ID = "msg_dev_repo_never_written"


async def test_begin_idempotency_wins_the_first_time() -> None:
    async with local_repo_table("developer") as table:
        repo = DeveloperDynamoRepo(table=table)

        assert await repo.begin_idempotency(USER_ID, IDEMPOTENCY_KEY, NOW) is True


async def test_begin_idempotency_loses_a_repeat_for_the_same_key() -> None:
    async with local_repo_table("developer") as table:
        repo = DeveloperDynamoRepo(table=table)
        await repo.begin_idempotency(USER_ID, IDEMPOTENCY_KEY, NOW)

        assert await repo.begin_idempotency(USER_ID, IDEMPOTENCY_KEY, NOW) is False


async def test_begin_idempotency_is_independent_per_key() -> None:
    async with local_repo_table("developer") as table:
        repo = DeveloperDynamoRepo(table=table)
        await repo.begin_idempotency(USER_ID, IDEMPOTENCY_KEY, NOW)

        assert await repo.begin_idempotency(USER_ID, "a-different-key", NOW) is True


async def test_peek_idempotency_is_none_for_a_key_never_begun() -> None:
    async with local_repo_table("developer") as table:
        repo = DeveloperDynamoRepo(table=table)

        assert await repo.peek_idempotency(USER_ID, IDEMPOTENCY_KEY) is None


async def test_peek_idempotency_is_in_flight_before_finish() -> None:
    async with local_repo_table("developer") as table:
        repo = DeveloperDynamoRepo(table=table)
        await repo.begin_idempotency(USER_ID, IDEMPOTENCY_KEY, NOW)

        record = await repo.peek_idempotency(USER_ID, IDEMPOTENCY_KEY)

        assert record is not None
        assert record.status is IdempotencyStatus.IN_FLIGHT
        assert record.response_status is None
        assert record.response_body is None


async def test_peek_idempotency_is_done_after_finish() -> None:
    async with local_repo_table("developer") as table:
        repo = DeveloperDynamoRepo(table=table)
        await repo.begin_idempotency(USER_ID, IDEMPOTENCY_KEY, NOW)

        await repo.finish_idempotency(USER_ID, IDEMPOTENCY_KEY, 201, '{"messageId":"msg_1"}')
        record = await repo.peek_idempotency(USER_ID, IDEMPOTENCY_KEY)

        assert record is not None
        assert record.status is IdempotencyStatus.DONE
        assert record.response_status == 201
        assert record.response_body == '{"messageId":"msg_1"}'


async def test_remember_api_campaign_id_wins_the_first_time() -> None:
    async with local_repo_table("developer") as table:
        repo = DeveloperDynamoRepo(table=table)

        assert await repo.remember_api_campaign_id(ACCOUNT_ID, CAMPAIGN_ID) is True
        assert await repo.api_campaign_id(ACCOUNT_ID) == CAMPAIGN_ID


async def test_remember_api_campaign_id_keeps_the_first_winner_on_a_race() -> None:
    async with local_repo_table("developer") as table:
        repo = DeveloperDynamoRepo(table=table)
        await repo.remember_api_campaign_id(ACCOUNT_ID, CAMPAIGN_ID)

        lost = await repo.remember_api_campaign_id(ACCOUNT_ID, OTHER_CAMPAIGN_ID)

        assert lost is False
        assert await repo.api_campaign_id(ACCOUNT_ID) == CAMPAIGN_ID


async def test_api_campaign_id_is_none_for_an_unprovisioned_account() -> None:
    async with local_repo_table("developer") as table:
        repo = DeveloperDynamoRepo(table=table)

        assert await repo.api_campaign_id(ACCOUNT_ID) is None


async def test_custom_strings_round_trip_through_a_batch_write_and_read() -> None:
    async with local_repo_table("developer") as table:
        repo = DeveloperDynamoRepo(table=table)

        await repo.remember_custom_strings({MESSAGE_ID: "order-1", OTHER_MESSAGE_ID: "order-2"})
        found = await repo.custom_strings_of([MESSAGE_ID, OTHER_MESSAGE_ID, UNWRITTEN_MESSAGE_ID])

        assert found == {MESSAGE_ID: "order-1", OTHER_MESSAGE_ID: "order-2"}


async def test_custom_strings_of_is_empty_for_no_matches() -> None:
    async with local_repo_table("developer") as table:
        repo = DeveloperDynamoRepo(table=table)

        assert await repo.custom_strings_of([UNWRITTEN_MESSAGE_ID]) == {}

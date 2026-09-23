from datetime import UTC, datetime
from typing import TYPE_CHECKING

from txtlocal.shared.table import n
from txtlocal.shared.testing import local_repo_table
from txtlocal.slices.identity.model import (
    Account,
    AccountSettings,
    MessagingSettings,
    Role,
    SubPointer,
    UnicodeMode,
    User,
    UserStatus,
)
from txtlocal.slices.identity.repo import (
    IdentityDynamoRepo,
    RateLimitsDynamoRepo,
    account_key,
    epoch_seconds,
    rate_limit_key,
)

if TYPE_CHECKING:
    from txtlocal.slices.identity.service import RateLimits

ACCOUNT_ID = "0199-account"
NOW = datetime(2026, 9, 19, 12, 0, 0, 123000, tzinfo=UTC)
OWNER_SUB = "owner-sub"
SUB_SUB = "sub-sub"
TRIAL_CREDIT = 2_000_000


def account() -> Account:
    return Account(account_id=ACCOUNT_ID, created_at=NOW, email="demo@txtlocal.local", name="demo")


def user(user_id: str, username: str, role: Role, digest: str) -> User:
    return User(
        account_id=ACCOUNT_ID,
        api_key_hash=digest,
        api_key_issued_at=NOW,
        api_key_prefix=digest[:8],
        cognito_sub=OWNER_SUB if role is Role.OWNER else None,
        created_at=NOW,
        role=role,
        status=UserStatus.ACTIVE if role is Role.OWNER else UserStatus.INVITED,
        user_id=user_id,
        username=username,
    )


def owner() -> User:
    return user("owner-id", "demo@txtlocal.local", Role.OWNER, "a" * 64)


def invited() -> User:
    return user("sub-id", "sub@txtlocal.local", Role.SUB, "b" * 64)


def pointer(sub: str, user_id: str) -> SubPointer:
    return SubPointer(account_id=ACCOUNT_ID, created_at=NOW, sub=sub, user_id=user_id)


async def test_create_account_is_put_if_absent() -> None:
    async with local_repo_table("identity") as table:
        repo = IdentityDynamoRepo(table)

        first = await repo.create_account(account(), owner(), pointer(OWNER_SUB, "owner-id"))
        second = await repo.create_account(account(), owner(), pointer(OWNER_SUB, "owner-id"))

    assert (first, second) == (True, False)


async def test_rows_round_trip_through_the_table() -> None:
    async with local_repo_table("identity") as table:
        repo = IdentityDynamoRepo(table)
        await repo.create_account(account(), owner(), pointer(OWNER_SUB, "owner-id"))

        read = (
            await repo.get_account(ACCOUNT_ID),
            await repo.get_user(ACCOUNT_ID, "owner-id"),
            await repo.get_pointer(OWNER_SUB),
        )

    assert read == (account(), owner(), pointer(OWNER_SUB, "owner-id"))


async def test_indexes_answer_username_and_api_key() -> None:
    async with local_repo_table("identity") as table:
        repo = IdentityDynamoRepo(table)
        await repo.create_account(account(), owner(), pointer(OWNER_SUB, "owner-id"))

        found = (
            await repo.find_user_by_username("demo@txtlocal.local"),
            await repo.find_user_by_api_key("a" * 64),
            await repo.find_user_by_username("nobody@txtlocal.local"),
            await repo.find_user_by_api_key("c" * 64),
        )

    assert found == (owner(), owner(), None, None)


async def test_saving_a_rotated_key_moves_the_index_entry() -> None:
    rotated = owner().model_copy(update={"api_key_hash": "c" * 64, "api_key_prefix": "cccccccc"})
    async with local_repo_table("identity") as table:
        repo = IdentityDynamoRepo(table)
        await repo.create_account(account(), owner(), pointer(OWNER_SUB, "owner-id"))

        saved = await repo.save_user(rotated)
        by_old = await repo.find_user_by_api_key("a" * 64)
        by_new = await repo.find_user_by_api_key("c" * 64)

    assert (saved, by_old, by_new) == (True, None, rotated)


async def test_save_user_needs_an_existing_row_and_put_user_needs_none() -> None:
    async with local_repo_table("identity") as table:
        repo = IdentityDynamoRepo(table)

        saved_missing = await repo.save_user(invited())
        put_first = await repo.put_user(invited())
        put_again = await repo.put_user(invited())

    assert (saved_missing, put_first, put_again) == (False, True, False)


async def test_save_account_updates_contact_fields() -> None:
    async with local_repo_table("identity") as table:
        repo = IdentityDynamoRepo(table)
        await repo.create_account(account(), owner(), pointer(OWNER_SUB, "owner-id"))

        updated = account().model_copy(
            update={"email": "billing@example.com", "mobile": "+447411972333", "name": "Billing"}
        )
        saved = await repo.save_account(updated)
        stored = await repo.get_account(ACCOUNT_ID)

    assert (saved, stored) == (True, updated)


async def test_save_account_needs_an_existing_row() -> None:
    async with local_repo_table("identity") as table:
        repo = IdentityDynamoRepo(table)

        assert await repo.save_account(account()) is False


async def test_link_user_wins_once() -> None:
    linked = invited().model_copy(
        update={"cognito_sub": SUB_SUB, "email_verified": True, "status": UserStatus.ACTIVE}
    )
    async with local_repo_table("identity") as table:
        repo = IdentityDynamoRepo(table)
        await repo.put_user(invited())

        first = await repo.link_user(linked, pointer(SUB_SUB, "sub-id"))
        second = await repo.link_user(linked, pointer(SUB_SUB, "sub-id"))
        stored = await repo.get_user(ACCOUNT_ID, "sub-id")
        mapped = await repo.get_pointer(SUB_SUB)

    assert (first, second) == (True, False)
    assert stored == linked
    assert mapped == pointer(SUB_SUB, "sub-id")


async def test_account_settings_leave_billing_attributes_alone() -> None:
    settings = AccountSettings(default_country="US", name="Acme", timezone="America/New_York")
    async with local_repo_table("identity") as table:
        repo = IdentityDynamoRepo(table)
        await repo.create_account(account(), owner(), pointer(OWNER_SUB, "owner-id"))
        await table.client.update_item(
            ExpressionAttributeValues={":credit": n(TRIAL_CREDIT)},
            Key=account_key(ACCOUNT_ID),
            TableName=table.name,
            UpdateExpression="ADD balanceMicro :credit",
        )

        updated = await repo.set_account_settings(ACCOUNT_ID, settings)
        stored = await repo.get_account(ACCOUNT_ID)

    assert updated is True
    assert stored == account().model_copy(
        update={
            "balance_micro": TRIAL_CREDIT,
            "name": "Acme",
            "settings": MessagingSettings(default_country="US"),
            "timezone": "America/New_York",
        }
    )


async def test_messaging_settings_replace_the_map() -> None:
    settings = MessagingSettings(
        max_parts=3, show_own_number=False, unicode_mode=UnicodeMode.GSM_ONLY
    )
    async with local_repo_table("identity") as table:
        repo = IdentityDynamoRepo(table)
        await repo.create_account(account(), owner(), pointer(OWNER_SUB, "owner-id"))

        updated = await repo.set_messaging_settings(ACCOUNT_ID, settings)
        missing = await repo.set_messaging_settings("no-such-account", settings)
        stored = await repo.get_account(ACCOUNT_ID)

    assert (updated, missing) == (True, False)
    assert stored is not None
    assert stored.settings == settings


async def test_list_users_reads_the_whole_partition() -> None:
    async with local_repo_table("identity") as table:
        repo = IdentityDynamoRepo(table)
        await repo.create_account(account(), owner(), pointer(OWNER_SUB, "owner-id"))
        await repo.put_user(invited())

        users = await repo.list_users(ACCOUNT_ID)

    assert sorted(users, key=lambda row: row.user_id) == [owner(), invited()]


def _fits_rate_limits(repo: RateLimitsDynamoRepo) -> RateLimits:
    return repo


async def test_rate_limit_counter_increments_per_user_and_minute() -> None:
    async with local_repo_table("identity") as table:
        repo = RateLimitsDynamoRepo(table)

        first = await repo.count("usr_1", "2026-09-20T12:00")
        second = await repo.count("usr_1", "2026-09-20T12:00")
        other_minute = await repo.count("usr_1", "2026-09-20T12:01")
        other_user = await repo.count("usr_2", "2026-09-20T12:00")

    assert (first, second, other_minute, other_user) == (1, 2, 1, 1)


async def test_rate_limit_counter_sets_a_two_day_ttl_from_the_minute() -> None:
    async with local_repo_table("identity") as table:
        repo = RateLimitsDynamoRepo(table)
        await repo.count("usr_1", "2026-09-20T12:00")

        stored = await table.client.get_item(
            Key=rate_limit_key("usr_1", "2026-09-20T12:00"), TableName=table.name
        )

    item = stored["Item"]
    expected_ttl = epoch_seconds(datetime(2026, 9, 22, 12, 0, tzinfo=UTC))
    assert int(item["ttl"]["N"]) == expected_ttl

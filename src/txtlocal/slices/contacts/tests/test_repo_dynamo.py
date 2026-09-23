import pytest

from txtlocal.shared.phone import E164
from txtlocal.shared.testing import local_repo_table
from txtlocal.slices.contacts.model import ContactList, ListKind
from txtlocal.slices.contacts.repo import ContactsDynamoRepo, ContactsRepo
from txtlocal.slices.contacts.tests.fakes import (
    ACCOUNT,
    NOW,
    OWNER_MOBILE,
    SECOND_MOBILE,
    THIRD_MOBILE,
    contact_of,
)

EXAMPLE = ContactList(created_at=NOW, list_id="list-1", name="Example List")
OPT_OUT = ContactList(created_at=NOW, kind=ListKind.OPT_OUT, list_id="list-2", name="Opt-Out List")
OWNER = contact_of(EXAMPLE.list_id, OWNER_MOBILE, "Sam", "Jones")
SECOND = contact_of(EXAMPLE.list_id, SECOND_MOBILE, "Ada")
IN_OTHER_LIST = contact_of(OPT_OUT.list_id, OWNER_MOBILE)


async def test_defaults_round_trip_through_the_table() -> None:
    async with local_repo_table("contacts") as table:
        repo: ContactsRepo = ContactsDynamoRepo(table)
        await repo.put_defaults_if_absent(ACCOUNT, EXAMPLE, OPT_OUT)

        assert await repo.list_lists(ACCOUNT) == [EXAMPLE, OPT_OUT]


async def test_defaults_second_put_loses_and_writes_nothing() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)
        first = await repo.put_defaults_if_absent(ACCOUNT, EXAMPLE, OPT_OUT)

        second = await repo.put_defaults_if_absent(
            ACCOUNT, EXAMPLE.model_copy(update={"name": "Renamed"}), OPT_OUT
        )

        assert (first, second) == (True, False)
        assert await repo.list_lists(ACCOUNT) == [EXAMPLE, OPT_OUT]


async def test_upsert_contact_inserts_once_and_counts_it() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)
        await repo.put_list(ACCOUNT, EXAMPLE)

        outcomes = (
            await repo.upsert_contact(OWNER),
            await repo.upsert_contact(OWNER.model_copy(update={"first_name": "Renamed"})),
        )

        held = await repo.get_list(ACCOUNT, EXAMPLE.list_id)
        assert outcomes == (True, False)
        assert held is not None
        assert held.contact_count == 1


async def test_upsert_contact_replaces_the_row_it_finds() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)
        await repo.put_list(ACCOUNT, EXAMPLE)
        await repo.upsert_contact(OWNER)

        renamed = OWNER.model_copy(update={"first_name": "Renamed"})
        await repo.upsert_contact(renamed)

        assert await repo.get_contact(EXAMPLE.list_id, E164(OWNER_MOBILE)) == renamed


async def test_delete_contact_wins_once_and_gives_the_count_back() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)
        await repo.put_list(ACCOUNT, EXAMPLE)
        await repo.upsert_contact(OWNER)

        outcomes = (
            await repo.delete_contact(ACCOUNT, EXAMPLE.list_id, E164(OWNER_MOBILE)),
            await repo.delete_contact(ACCOUNT, EXAMPLE.list_id, E164(OWNER_MOBILE)),
        )

        held = await repo.get_list(ACCOUNT, EXAMPLE.list_id)
        assert outcomes == (True, False)
        assert held is not None
        assert held.contact_count == 0


async def test_contacts_with_mobile_finds_every_list_holding_the_number() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)
        await repo.put_contacts([OWNER, IN_OTHER_LIST, SECOND])

        found = await repo.contacts_with_mobile(ACCOUNT, E164(OWNER_MOBILE))

        assert sorted(one.list_id for one in found) == [EXAMPLE.list_id, OPT_OUT.list_id]


async def test_all_contacts_reads_the_list_in_sort_key_order() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)
        await repo.put_contacts([OWNER, SECOND])

        held = await repo.all_contacts(EXAMPLE.list_id)

        assert [one.mobile for one in held] == [SECOND_MOBILE, OWNER_MOBILE]


async def test_list_contacts_pages_by_cursor() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)
        await repo.put_contacts([OWNER, SECOND])

        first = await repo.list_contacts(EXAMPLE.list_id, None, 1)
        second = await repo.list_contacts(EXAMPLE.list_id, first.cursor, 1)
        third = await repo.list_contacts(EXAMPLE.list_id, second.cursor, 1)

        assert [one.mobile for one in first.items] == [SECOND_MOBILE]
        assert [one.mobile for one in second.items] == [OWNER_MOBILE]
        assert (third.cursor, third.items) == (None, [])


async def test_existing_mobiles_answers_only_the_rows_the_list_holds() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)
        await repo.put_contacts([OWNER])

        found = await repo.existing_mobiles(
            EXAMPLE.list_id, [E164(OWNER_MOBILE), E164(THIRD_MOBILE)]
        )

        assert found == frozenset({OWNER_MOBILE})


async def test_delete_contacts_removes_the_batch() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)
        await repo.put_contacts([OWNER, SECOND])

        await repo.delete_contacts(EXAMPLE.list_id, [E164(OWNER_MOBILE), E164(SECOND_MOBILE)])

        assert await repo.all_contacts(EXAMPLE.list_id) == []


async def test_put_contacts_writes_past_the_batch_size() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)
        many = [contact_of(EXAMPLE.list_id, f"+4474119{index:05d}") for index in range(30)]

        await repo.put_contacts(many)

        assert len(await repo.all_contacts(EXAMPLE.list_id)) == 30


async def test_add_count_moves_the_counter_both_ways() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)
        await repo.put_list(ACCOUNT, EXAMPLE)

        await repo.add_count(ACCOUNT, EXAMPLE.list_id, 5)
        await repo.add_count(ACCOUNT, EXAMPLE.list_id, -2)

        held = await repo.get_list(ACCOUNT, EXAMPLE.list_id)
        assert held is not None
        assert held.contact_count == 3


async def test_add_count_raises_no_list_row_from_the_dead() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)

        counted = await repo.add_count(ACCOUNT, EXAMPLE.list_id, 1)

        assert await repo.list_lists(ACCOUNT) == []
        assert counted is False


async def test_upsert_contact_raises_no_list_row_from_the_dead() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)

        inserted = await repo.upsert_contact(OWNER)

        assert await repo.list_lists(ACCOUNT) == []
        assert inserted is False


async def test_existing_mobiles_sees_a_row_written_a_moment_earlier() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)
        await repo.put_contacts([OWNER])

        found = await repo.existing_mobiles(EXAMPLE.list_id, [E164(OWNER_MOBILE)])

        assert found == frozenset({OWNER_MOBILE})


@pytest.mark.parametrize(
    ("list_id", "expected"),
    [(EXAMPLE.list_id, True), ("missing", False)],
    ids=["present-row-renames", "missing-row-is-false"],
)
async def test_rename_list(list_id: str, expected: bool) -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)
        await repo.put_list(ACCOUNT, EXAMPLE)

        renamed = await repo.rename_list(ACCOUNT, list_id, "Customers")

        assert renamed is expected


async def test_delete_list_wins_once() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)
        await repo.put_list(ACCOUNT, EXAMPLE)

        outcomes = (
            await repo.delete_list(ACCOUNT, EXAMPLE.list_id),
            await repo.delete_list(ACCOUNT, EXAMPLE.list_id),
        )

        assert outcomes == (True, False)


async def test_get_contact_is_none_for_a_missing_row() -> None:
    async with local_repo_table("contacts") as table:
        repo = ContactsDynamoRepo(table)

        assert await repo.get_contact(EXAMPLE.list_id, E164(OWNER_MOBILE)) is None

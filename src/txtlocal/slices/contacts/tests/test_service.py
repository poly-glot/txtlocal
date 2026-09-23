from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Protocol

import pytest

from txtlocal.shared.errors import AppError, BadRequest, Conflict, NotFound
from txtlocal.shared.phone import E164, INVALID_NUMBER_MESSAGE
from txtlocal.slices.contacts.model import (
    BulkAction,
    BulkRequest,
    CleanUpAction,
    CleanUpRequest,
    ContactInput,
    ContactList,
    ImportRequest,
    ListKind,
    ListRequest,
    Recipient,
)
from txtlocal.slices.contacts.service import (
    CONTACT_NOT_FOUND,
    CUSTOM_FIELD_LENGTH,
    DUPLICATE_LIST_NAME,
    EXAMPLE_LIST,
    FIRST_NAME_LENGTH,
    INVALID_EMAIL,
    LAST_NAME_LENGTH,
    LIST_CEILING,
    LIST_FULL,
    LIST_NAME_LENGTH,
    LIST_NOT_FOUND,
    OPT_OUT_LIST,
    OPT_OUT_NOT_CLEANABLE,
    OPT_OUT_NOT_DELETABLE,
    OPT_OUT_NOT_RENAMABLE,
    TOO_MANY_IDS,
    TOO_MANY_ROWS,
    ContactsService,
    OwnerLookup,
    Settings,
    moved_message,
    removed_message,
)
from txtlocal.slices.contacts.tests.fakes import (
    ACCOUNT,
    NOW,
    OTHER_ACCOUNT,
    OWNER_MOBILE,
    SECOND_MOBILE,
    THIRD_MOBILE,
    US_MOBILE,
    InMemoryContactsRepo,
    StubOwner,
    StubOwners,
    StubSettings,
    contact_of,
)
from txtlocal.slices.identity.model import MessagingSettings

if TYPE_CHECKING:
    from txtlocal.slices.campaigns.service import Contacts
    from txtlocal.slices.identity.service import AccountHook, IdentityService
    from txtlocal.slices.messaging.service import OptOuts


class Recipients(Protocol):
    async def opt_outs(self, account_id: str) -> frozenset[E164]: ...

    async def recipients_of(self, account_id: str, list_id: str) -> list[Recipient]: ...


def _fits_opt_outs(service: ContactsService) -> OptOuts:
    return service


async def list_row(service: ContactsService, list_id: str) -> ContactList:
    return next(one for one in await service.lists(ACCOUNT, None) if one.list_id == list_id)


def _fits_recipients(service: ContactsService) -> Recipients:
    return service


def _fits_campaign_contacts(service: ContactsService) -> Contacts:
    return service


def _fits_account_hook(service: ContactsService) -> AccountHook:
    return service.provision_defaults


def _fits_owner_lookup(identity: IdentityService) -> OwnerLookup:
    return identity


def _fits_settings(identity: IdentityService) -> Settings:
    return identity


def _fits_stub_owners(owners: StubOwners) -> OwnerLookup:
    return owners


def row(mobile: str, first_name: str = "", last_name: str = "", **fields: str) -> ContactInput:
    return ContactInput(first_name=first_name, last_name=last_name, mobile=mobile, **fields)


def generated(count: int) -> list[ContactInput]:
    return [row(f"+4474119{index:05d}") for index in range(count)]


async def test_provision_defaults_creates_the_lists_sign_up_promises(
    provisioned: ContactsService,
) -> None:
    lists = await provisioned.lists(ACCOUNT, None)

    assert [(one.name, one.kind) for one in lists] == [
        (EXAMPLE_LIST, ListKind.STANDARD),
        (OPT_OUT_LIST, ListKind.OPT_OUT),
    ]


async def test_provision_defaults_puts_the_owner_in_the_example_list(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    page = await provisioned.contacts(ACCOUNT, example_list.list_id, None, None, 20)

    assert [(one.first_name, one.last_name, one.mobile) for one in page.items] == [
        ("Sam", "Jones", OWNER_MOBILE)
    ]


async def test_provision_defaults_counts_the_owner_on_the_list_row(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    summary = await list_row(provisioned, example_list.list_id)

    assert (summary.contact_count, summary.list_id, summary.name) == (
        1,
        example_list.list_id,
        EXAMPLE_LIST,
    )


async def test_provision_defaults_without_a_mobile_leaves_the_example_list_empty(
    owners: StubOwners, service: ContactsService
) -> None:
    owners.by_account[ACCOUNT] = StubOwner(mobile=None)

    await service.provision_defaults(ACCOUNT, NOW)

    lists = await service.lists(ACCOUNT, None)
    assert [one.contact_count for one in lists] == [0, 0]


async def test_provision_defaults_runs_once_per_account(provisioned: ContactsService) -> None:
    await provisioned.provision_defaults(ACCOUNT, NOW)

    assert len(await provisioned.lists(ACCOUNT, None)) == 2


async def test_opt_out_adds_the_number_to_the_opt_out_list(
    provisioned: ContactsService,
) -> None:
    await provisioned.opt_out(ACCOUNT, E164(SECOND_MOBILE), NOW)

    assert await provisioned.opt_outs(ACCOUNT) == frozenset({SECOND_MOBILE})


async def test_opt_out_twice_holds_one_row(
    provisioned: ContactsService, opt_out_list: ContactList
) -> None:
    await provisioned.opt_out(ACCOUNT, E164(SECOND_MOBILE), NOW)
    await provisioned.opt_out(ACCOUNT, E164(SECOND_MOBILE), NOW)

    summary = await list_row(provisioned, opt_out_list.list_id)
    assert summary.contact_count == 1


async def test_opt_outs_is_empty_before_anyone_opts_out(provisioned: ContactsService) -> None:
    assert await provisioned.opt_outs(ACCOUNT) == frozenset()


@pytest.mark.parametrize(
    ("destination", "expected"),
    [(SECOND_MOBILE, True), (THIRD_MOBILE, False)],
    ids=["opted-out-number", "other-number"],
)
async def test_is_opted_out_answers_per_destination(
    provisioned: ContactsService, destination: str, expected: bool
) -> None:
    await provisioned.opt_out(ACCOUNT, E164(SECOND_MOBILE), NOW)

    assert await provisioned.is_opted_out(ACCOUNT, E164(destination)) is expected


async def test_is_opted_out_resolves_the_opt_out_list_once_per_account(
    provisioned: ContactsService, repo: InMemoryContactsRepo
) -> None:
    await provisioned.is_opted_out(ACCOUNT, E164(SECOND_MOBILE))
    resolved = repo.list_queries

    await provisioned.is_opted_out(ACCOUNT, E164(THIRD_MOBILE))

    assert repo.list_queries == resolved


async def test_each_account_resolves_its_own_opt_out_list(
    owners: StubOwners, service: ContactsService
) -> None:
    owners.by_account[OTHER_ACCOUNT] = StubOwner(mobile=None)
    await service.provision_defaults(ACCOUNT, NOW)
    await service.provision_defaults(OTHER_ACCOUNT, NOW)
    await service.opt_out(ACCOUNT, E164(SECOND_MOBILE), NOW)

    opted_out = (
        await service.is_opted_out(ACCOUNT, E164(SECOND_MOBILE)),
        await service.is_opted_out(OTHER_ACCOUNT, E164(SECOND_MOBILE)),
    )

    assert opted_out == (True, False)
    assert await service.opt_outs(OTHER_ACCOUNT) == frozenset()


async def test_an_account_provisioned_later_still_resolves_its_opt_out_list(
    service: ContactsService,
) -> None:
    before = await service.is_opted_out(ACCOUNT, E164(SECOND_MOBILE))

    await service.provision_defaults(ACCOUNT, NOW)
    await service.opt_out(ACCOUNT, E164(SECOND_MOBILE), NOW)

    assert before is False
    assert await service.is_opted_out(ACCOUNT, E164(SECOND_MOBILE)) is True


async def test_create_list_adds_an_empty_list(provisioned: ContactsService) -> None:
    created = await provisioned.create_list(ACCOUNT, ListRequest(name="Leads"))

    assert (created.contact_count, created.kind, created.name) == (0, ListKind.STANDARD, "Leads")


async def test_create_list_refuses_a_name_the_account_already_uses(
    provisioned: ContactsService,
) -> None:
    with pytest.raises(Conflict) as caught:
        await provisioned.create_list(ACCOUNT, ListRequest(name="example list"))

    assert str(caught.value) == DUPLICATE_LIST_NAME


async def test_rename_list_changes_the_name(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    renamed = await provisioned.rename_list(
        ACCOUNT, example_list.list_id, ListRequest(name="Customers")
    )

    assert renamed.name == "Customers"
    assert [one.name for one in await provisioned.lists(ACCOUNT, None)] == [
        "Customers",
        OPT_OUT_LIST,
    ]


async def test_rename_refuses_the_opt_out_list(
    provisioned: ContactsService, opt_out_list: ContactList
) -> None:
    with pytest.raises(Conflict) as caught:
        await provisioned.rename_list(ACCOUNT, opt_out_list.list_id, ListRequest(name="Blocked"))

    assert str(caught.value) == OPT_OUT_NOT_RENAMABLE


async def test_delete_refuses_the_opt_out_list(
    provisioned: ContactsService, opt_out_list: ContactList
) -> None:
    with pytest.raises(Conflict) as caught:
        await provisioned.delete_list(ACCOUNT, opt_out_list.list_id)

    assert str(caught.value) == OPT_OUT_NOT_DELETABLE


async def test_delete_list_takes_its_contacts_with_it(
    provisioned: ContactsService, example_list: ContactList, repo: InMemoryContactsRepo
) -> None:
    await provisioned.delete_list(ACCOUNT, example_list.list_id)

    assert [one.name for one in await provisioned.lists(ACCOUNT, None)] == [OPT_OUT_LIST]
    assert await repo.all_contacts(example_list.list_id) == []


async def test_lists_filters_by_name(provisioned: ContactsService) -> None:
    found = await provisioned.lists(ACCOUNT, "opt")

    assert [one.name for one in found] == [OPT_OUT_LIST]


async def test_add_contact_normalises_the_mobile(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    added = await provisioned.add_contact(ACCOUNT, example_list.list_id, row("07411 972300", "Ada"))

    assert (added.first_name, added.mobile, added.updated_at) == ("Ada", SECOND_MOBILE, NOW)


async def test_add_contact_uses_the_account_default_country(
    account_settings: StubSettings, provisioned: ContactsService, example_list: ContactList
) -> None:
    account_settings.by_account[ACCOUNT] = MessagingSettings(default_country="US")

    added = await provisioned.add_contact(ACCOUNT, example_list.list_id, row("(202) 555-0123"))

    assert added.mobile == US_MOBILE


async def test_a_mobile_already_in_the_list_updates_rather_than_inserts(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    await provisioned.add_contact(ACCOUNT, example_list.list_id, row(OWNER_MOBILE, "Renamed"))

    page = await provisioned.contacts(ACCOUNT, example_list.list_id, None, None, 20)
    summary = await list_row(provisioned, example_list.list_id)
    assert [one.first_name for one in page.items] == ["Renamed"]
    assert summary.contact_count == 1


async def test_the_same_mobile_in_two_lists_is_two_rows(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    other = await provisioned.create_list(ACCOUNT, ListRequest(name="Leads"))

    await provisioned.add_contact(ACCOUNT, other.list_id, row(OWNER_MOBILE))

    counts = (
        (await list_row(provisioned, example_list.list_id)).contact_count,
        (await list_row(provisioned, other.list_id)).contact_count,
    )
    assert counts == (1, 1)


async def test_update_contact_moves_the_row_when_the_mobile_changes(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    await provisioned.update_contact(
        ACCOUNT, example_list.list_id, OWNER_MOBILE, row(SECOND_MOBILE, "Sam")
    )

    page = await provisioned.contacts(ACCOUNT, example_list.list_id, None, None, 20)
    summary = await list_row(provisioned, example_list.list_id)
    assert [one.mobile for one in page.items] == [SECOND_MOBILE]
    assert summary.contact_count == 1


async def test_remove_contact_drops_the_row_and_its_count(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    await provisioned.remove_contact(ACCOUNT, example_list.list_id, OWNER_MOBILE)

    summary = await list_row(provisioned, example_list.list_id)
    page = await provisioned.contacts(ACCOUNT, example_list.list_id, None, None, 20)
    assert (summary.contact_count, page.items) == (0, [])


async def test_contacts_pages_by_cursor(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    await provisioned.add_contact(ACCOUNT, example_list.list_id, row(SECOND_MOBILE))

    first = await provisioned.contacts(ACCOUNT, example_list.list_id, None, None, 1)
    second = await provisioned.contacts(ACCOUNT, example_list.list_id, None, first.cursor, 1)

    assert [one.mobile for one in first.items] == [SECOND_MOBILE]
    assert [one.mobile for one in second.items] == [OWNER_MOBILE]


@pytest.mark.parametrize(
    ("needle", "expected"),
    [("Ada", [SECOND_MOBILE]), ("+44741197233", [OWNER_MOBILE]), ("zzz", [])],
    ids=["name-substring", "mobile-prefix", "no-match"],
)
async def test_contacts_filters_the_page(
    provisioned: ContactsService, example_list: ContactList, needle: str, expected: list[str]
) -> None:
    await provisioned.add_contact(ACCOUNT, example_list.list_id, row(SECOND_MOBILE, "Ada"))

    page = await provisioned.contacts(ACCOUNT, example_list.list_id, needle, None, 20)

    assert [one.mobile for one in page.items] == expected


@pytest.mark.parametrize(
    ("limit", "expected"),
    [(100, 100), (101, 100)],
    ids=["page-of-100", "page-of-101-clamps"],
)
async def test_contacts_clamps_the_page_size(
    provisioned: ContactsService, example_list: ContactList, limit: int, expected: int
) -> None:
    await provisioned.import_contacts(
        ACCOUNT, example_list.list_id, ImportRequest(rows=generated(150))
    )

    page = await provisioned.contacts(ACCOUNT, example_list.list_id, None, None, limit)

    assert len(page.items) == expected


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("first_name", "a" * 50),
        ("last_name", "a" * 50),
        ("cf1", "a" * 100),
        ("email", "sam@example.com"),
    ],
    ids=["first-name-50", "last-name-50", "custom-field-100", "email-with-at"],
)
async def test_the_last_accepted_field_value(
    provisioned: ContactsService, example_list: ContactList, field: str, value: str
) -> None:
    added = await provisioned.add_contact(
        ACCOUNT, example_list.list_id, row(SECOND_MOBILE, **{field: value})
    )

    assert getattr(added, field) == value


@pytest.mark.parametrize(
    ("mobile", "fields", "error", "message"),
    [
        ("nope", {}, BadRequest, INVALID_NUMBER_MESSAGE),
        (SECOND_MOBILE, {"first_name": "a" * 51}, BadRequest, FIRST_NAME_LENGTH),
        (SECOND_MOBILE, {"last_name": "a" * 51}, BadRequest, LAST_NAME_LENGTH),
        (SECOND_MOBILE, {"cf1": "a" * 101}, BadRequest, CUSTOM_FIELD_LENGTH),
        (SECOND_MOBILE, {"email": "sam.example.com"}, BadRequest, INVALID_EMAIL),
    ],
    ids=[
        "mobile-does-not-parse",
        "first-name-51",
        "last-name-51",
        "custom-field-101",
        "email-without-at",
    ],
)
async def test_add_contact_refusals_carry_their_copy(
    provisioned: ContactsService,
    example_list: ContactList,
    mobile: str,
    fields: dict[str, str],
    error: type[AppError],
    message: str,
) -> None:
    with pytest.raises(error) as caught:
        await provisioned.add_contact(ACCOUNT, example_list.list_id, row(mobile, **fields))

    assert str(caught.value) == message


@pytest.mark.parametrize(
    "name",
    ["", " ", "a" * 101],
    ids=["empty", "blank", "101-characters"],
)
async def test_list_name_refusals_carry_their_copy(provisioned: ContactsService, name: str) -> None:
    with pytest.raises(BadRequest) as caught:
        await provisioned.create_list(ACCOUNT, ListRequest(name=name))

    assert str(caught.value) == LIST_NAME_LENGTH


async def test_a_list_name_of_100_characters_is_accepted(provisioned: ContactsService) -> None:
    created = await provisioned.create_list(ACCOUNT, ListRequest(name="a" * 100))

    assert created.name == "a" * 100


async def test_import_reports_imported_updated_and_skipped(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    rows = [row(SECOND_MOBILE, "Ada"), row(OWNER_MOBILE, "Sam"), row("nope")]

    report = await provisioned.import_contacts(
        ACCOUNT, example_list.list_id, ImportRequest(rows=rows)
    )

    assert report.message == "Imported 1, updated 1, skipped 1 invalid"
    assert (report.imported, report.updated, report.skipped) == (1, 1, 1)


async def test_import_counts_a_number_already_in_the_list_under_updated(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    report = await provisioned.import_contacts(
        ACCOUNT, example_list.list_id, ImportRequest(rows=[row(OWNER_MOBILE, "Sam")])
    )

    assert (report.imported, report.updated) == (0, 1)


async def test_import_accepts_500_rows(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    report = await provisioned.import_contacts(
        ACCOUNT, example_list.list_id, ImportRequest(rows=generated(500))
    )

    assert report.imported == 500


async def test_import_refuses_501_rows(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    with pytest.raises(BadRequest) as caught:
        await provisioned.import_contacts(
            ACCOUNT, example_list.list_id, ImportRequest(rows=generated(501))
        )

    assert str(caught.value) == TOO_MANY_ROWS


async def test_a_list_holds_the_ten_thousandth_contact(
    provisioned: ContactsService, example_list: ContactList, repo: InMemoryContactsRepo
) -> None:
    await repo.add_count(ACCOUNT, example_list.list_id, LIST_CEILING - 2)

    await provisioned.add_contact(ACCOUNT, example_list.list_id, row(SECOND_MOBILE))

    summary = await list_row(provisioned, example_list.list_id)
    assert summary.contact_count == LIST_CEILING


async def test_a_list_refuses_the_ten_thousand_and_first_contact(
    provisioned: ContactsService, example_list: ContactList, repo: InMemoryContactsRepo
) -> None:
    await repo.add_count(ACCOUNT, example_list.list_id, LIST_CEILING - 1)

    with pytest.raises(BadRequest) as caught:
        await provisioned.add_contact(ACCOUNT, example_list.list_id, row(SECOND_MOBILE))

    assert str(caught.value) == LIST_FULL


async def test_a_full_list_still_updates_a_contact_it_holds(
    provisioned: ContactsService, example_list: ContactList, repo: InMemoryContactsRepo
) -> None:
    await repo.add_count(ACCOUNT, example_list.list_id, LIST_CEILING - 1)

    updated = await provisioned.add_contact(
        ACCOUNT, example_list.list_id, row(OWNER_MOBILE, "Renamed")
    )

    assert updated.first_name == "Renamed"


async def test_import_refuses_the_rows_past_the_ceiling(
    provisioned: ContactsService, example_list: ContactList, repo: InMemoryContactsRepo
) -> None:
    await repo.add_count(ACCOUNT, example_list.list_id, LIST_CEILING - 1)

    with pytest.raises(BadRequest) as caught:
        await provisioned.import_contacts(
            ACCOUNT, example_list.list_id, ImportRequest(rows=generated(2))
        )

    assert str(caught.value) == LIST_FULL


async def test_bulk_delete_removes_the_selected_contacts(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    await provisioned.add_contact(ACCOUNT, example_list.list_id, row(SECOND_MOBILE))

    result = await provisioned.bulk(
        ACCOUNT,
        example_list.list_id,
        BulkRequest(action=BulkAction.DELETE, contact_ids=[OWNER_MOBILE, SECOND_MOBILE]),
    )

    assert result.message == "Removed 2 contacts"
    assert (await list_row(provisioned, example_list.list_id)).contact_count == 0


async def test_bulk_delete_counts_only_the_rows_the_list_holds(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    result = await provisioned.bulk(
        ACCOUNT,
        example_list.list_id,
        BulkRequest(action=BulkAction.DELETE, contact_ids=[OWNER_MOBILE, THIRD_MOBILE]),
    )

    assert result.message == "Removed 1 contact"


async def test_bulk_opt_out_moves_them_to_the_opt_out_list(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    result = await provisioned.bulk(
        ACCOUNT,
        example_list.list_id,
        BulkRequest(action=BulkAction.OPT_OUT, contact_ids=[OWNER_MOBILE]),
    )

    assert result.message == "Moved 1 contact to the opt-out list"
    assert await provisioned.opt_outs(ACCOUNT) == frozenset({OWNER_MOBILE})
    assert (await list_row(provisioned, example_list.list_id)).contact_count == 0


async def test_bulk_accepts_100_ids(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    ids = [one.mobile for one in generated(100)]

    result = await provisioned.bulk(
        ACCOUNT, example_list.list_id, BulkRequest(action=BulkAction.DELETE, contact_ids=ids)
    )

    assert result.removed == 0


async def test_bulk_refuses_101_ids(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    ids = [one.mobile for one in generated(101)]

    with pytest.raises(BadRequest) as caught:
        await provisioned.bulk(
            ACCOUNT, example_list.list_id, BulkRequest(action=BulkAction.DELETE, contact_ids=ids)
        )

    assert str(caught.value) == TOO_MANY_IDS


async def test_clean_up_removes_invalid_numbers(
    provisioned: ContactsService, example_list: ContactList, repo: InMemoryContactsRepo
) -> None:
    await repo.upsert_contact(contact_of(example_list.list_id, "+44"))

    result = await provisioned.clean_up(
        ACCOUNT, example_list.list_id, CleanUpRequest(action=CleanUpAction.INVALID)
    )

    assert result.message == "Removed 1 contact"
    assert [one.mobile for one in await repo.all_contacts(example_list.list_id)] == [OWNER_MOBILE]


async def test_clean_up_removes_opted_out_contacts(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    await provisioned.opt_out(ACCOUNT, E164(OWNER_MOBILE), NOW)

    result = await provisioned.clean_up(
        ACCOUNT, example_list.list_id, CleanUpRequest(action=CleanUpAction.OPTED_OUT)
    )

    assert result.message == "Removed 1 contact"
    assert (await list_row(provisioned, example_list.list_id)).contact_count == 0


async def test_clean_up_refuses_the_opt_out_list(
    provisioned: ContactsService, opt_out_list: ContactList
) -> None:
    with pytest.raises(Conflict) as caught:
        await provisioned.clean_up(
            ACCOUNT, opt_out_list.list_id, CleanUpRequest(action=CleanUpAction.OPTED_OUT)
        )

    assert str(caught.value) == OPT_OUT_NOT_CLEANABLE


async def test_recipients_of_carries_every_placeholder_field(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    recipients = await provisioned.recipients_of(ACCOUNT, example_list.list_id)

    assert recipients == [
        Recipient(
            contact_id=OWNER_MOBILE,
            fields={
                "cf1": "",
                "cf2": "",
                "cf3": "",
                "cf4": "",
                "email": "demo@txtlocal.local",
                "first_name": "Sam",
                "last_name": "Jones",
                "mobile": OWNER_MOBILE,
            },
            mobile=OWNER_MOBILE,
        )
    ]


async def test_names_of_resolves_a_known_contact_and_skips_an_unknown_number(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    del example_list
    names = await provisioned.names_of(ACCOUNT, [E164(OWNER_MOBILE), E164("+447400123199")])

    assert names == {OWNER_MOBILE: "Sam Jones"}


@pytest.mark.parametrize(
    ("needle", "expected"),
    [
        ("Ada", [SECOND_MOBILE]),
        ("07411 972300", [SECOND_MOBILE]),
        ("+4474119723", [OWNER_MOBILE, SECOND_MOBILE]),
        ("nobody", []),
    ],
    ids=["by-name", "by-typed-number", "by-mobile-prefix", "no-match"],
)
async def test_search_finds_contacts_across_the_lists(
    provisioned: ContactsService, example_list: ContactList, needle: str, expected: list[str]
) -> None:
    await provisioned.add_contact(ACCOUNT, example_list.list_id, row(SECOND_MOBILE, "Ada"))

    hits = await provisioned.search(ACCOUNT, needle, 10)

    assert sorted(one.mobile for one in hits) == sorted(expected)


async def test_search_leaves_the_opt_out_list_out(provisioned: ContactsService) -> None:
    await provisioned.opt_out(ACCOUNT, E164(SECOND_MOBILE), NOW)

    hits = await provisioned.search(ACCOUNT, "+447411972300", 10)

    assert hits == []


@pytest.mark.parametrize(("limit", "expected"), [(25, 25), (26, 25)], ids=["25", "26-clamps"])
async def test_search_clamps_the_limit(
    provisioned: ContactsService, example_list: ContactList, limit: int, expected: int
) -> None:
    await provisioned.import_contacts(
        ACCOUNT, example_list.list_id, ImportRequest(rows=generated(30))
    )

    hits = await provisioned.search(ACCOUNT, "+4474119", limit)

    assert len(hits) == expected


async def test_export_writes_a_header_and_a_row_per_contact(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    csv = await provisioned.export(ACCOUNT, example_list.list_id)

    assert csv == (
        "mobile,first_name,last_name,email,cf1,cf2,cf3,cf4\n"
        f"{OWNER_MOBILE},Sam,Jones,demo@txtlocal.local,,,,\n"
    )


@pytest.mark.parametrize(
    "call",
    [
        lambda service: service.contacts(ACCOUNT, "missing", None, None, 20),
        lambda service: service.export(ACCOUNT, "missing"),
        lambda service: service.recipients_of(ACCOUNT, "missing"),
        lambda service: service.remove_contact(ACCOUNT, "missing", OWNER_MOBILE),
        lambda service: service.add_contact(ACCOUNT, "missing", row(SECOND_MOBILE)),
    ],
    ids=["page", "export", "recipients", "remove", "add"],
)
async def test_an_unknown_list_is_not_found(
    provisioned: ContactsService, call: Callable[[ContactsService], Awaitable[object]]
) -> None:
    with pytest.raises(NotFound) as caught:
        await call(provisioned)

    assert str(caught.value) == LIST_NOT_FOUND


async def test_removing_a_contact_the_list_does_not_hold_is_not_found(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    with pytest.raises(NotFound) as caught:
        await provisioned.remove_contact(ACCOUNT, example_list.list_id, SECOND_MOBILE)

    assert str(caught.value) == CONTACT_NOT_FOUND


async def test_updating_a_contact_the_list_does_not_hold_is_not_found(
    provisioned: ContactsService, example_list: ContactList
) -> None:
    with pytest.raises(NotFound) as caught:
        await provisioned.update_contact(
            ACCOUNT, example_list.list_id, SECOND_MOBILE, row(SECOND_MOBILE)
        )

    assert str(caught.value) == CONTACT_NOT_FOUND


@pytest.mark.parametrize(
    ("count", "expected"),
    [(0, "Removed 0 contacts"), (1, "Removed 1 contact"), (2, "Removed 2 contacts")],
    ids=["none", "one", "many"],
)
def test_removed_message_counts_contacts(count: int, expected: str) -> None:
    assert removed_message(count) == expected


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, "Moved 0 contacts to the opt-out list"),
        (1, "Moved 1 contact to the opt-out list"),
        (2, "Moved 2 contacts to the opt-out list"),
    ],
    ids=["none", "one", "many"],
)
def test_moved_message_counts_contacts(count: int, expected: str) -> None:
    assert moved_message(count) == expected

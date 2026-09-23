import csv
import io
import uuid
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Protocol, assert_never

from txtlocal.shared.errors import BadRequest, Conflict, Internal, NotFound
from txtlocal.shared.phone import E164, normalise
from txtlocal.slices.contacts.model import (
    EXPORT_COLUMNS,
    ActionResult,
    BulkAction,
    BulkRequest,
    CleanUpAction,
    CleanUpRequest,
    Contact,
    ContactHit,
    ContactInput,
    ContactList,
    ContactPage,
    ImportReport,
    ImportRequest,
    ListKind,
    ListRequest,
    Recipient,
    export_row,
    hit_of,
    recipient_of,
)

if TYPE_CHECKING:
    from txtlocal.shared.clock import Clock
    from txtlocal.slices.contacts.repo import ContactsRepo
    from txtlocal.slices.identity.model import MessagingSettings

CONTACT_NOT_FOUND = "Contact not found"
CUSTOM_FIELD_LENGTH = "A custom field can be at most 100 characters"
DEFAULT_COUNTRY = "GB"
DUPLICATE_LIST_NAME = "You already have a list with that name"
EXAMPLE_LIST = "Example List"
FIRST_NAME_LENGTH = "Enter a first name of 1 to 50 characters"
IMPORT_CEILING = 500
INVALID_EMAIL = "Enter a valid email address"
LAST_NAME_LENGTH = "Enter a last name of 1 to 50 characters"
LIST_CEILING = 10_000
LIST_FULL = "A list holds up to 10,000 contacts"
LIST_NAME_LENGTH = "Enter a list name of 1 to 100 characters"
LIST_NOT_FOUND = "List not found"
MAX_BULK = 100
MAX_CUSTOM_FIELD = 100
MAX_LIST_NAME = 100
MAX_NAME = 50
MAX_PAGE_SIZE = 100
OPT_OUT_CACHE_SIZE = 1024
OPT_OUT_LIST = "Opt-Out List"
OPT_OUT_LIST_MISSING = "the account has no opt-out list"
OPT_OUT_NOT_CLEANABLE = "The opt-out list cannot be cleaned up"
OPT_OUT_NOT_DELETABLE = "The opt-out list cannot be deleted"
OPT_OUT_NOT_RENAMABLE = "The opt-out list cannot be renamed"
PAGE_SIZE = 20
SEARCH_LIMIT = 25
SEARCH_SCAN = 100
TOO_MANY_IDS = "Select at most 100 contacts"
TOO_MANY_ROWS = "Import at most 500 rows at a time"


class Owner(Protocol):
    @property
    def email(self) -> str: ...

    @property
    def first_name(self) -> str: ...

    @property
    def last_name(self) -> str: ...

    @property
    def mobile(self) -> str | None: ...


class OwnerLookup(Protocol):
    async def owner_of(self, account_id: str) -> Owner: ...


class Settings(Protocol):
    async def messaging_settings(self, account_id: str) -> MessagingSettings: ...


def new_id() -> str:
    return str(uuid.uuid7())


def normalised_or_none(raw: str, country: str) -> E164 | None:
    text = raw.strip()
    if not text:
        return None

    try:
        return normalise(text, country)
    except BadRequest:
        return None


def checked_name(value: str, message: str) -> str:
    name = value.strip()
    if len(name) > MAX_NAME:
        raise BadRequest(message)
    return name


def checked_custom(value: str) -> str:
    custom = value.strip()
    if len(custom) > MAX_CUSTOM_FIELD:
        raise BadRequest(CUSTOM_FIELD_LENGTH)
    return custom


def checked_email(value: str) -> str:
    email = value.strip()
    if email and "@" not in email:
        raise BadRequest(INVALID_EMAIL)
    return email


def checked_list_name(value: str) -> str:
    name = value.strip()
    if not 1 <= len(name) <= MAX_LIST_NAME:
        raise BadRequest(LIST_NAME_LENGTH)
    return name


def contact_of(
    account_id: str, list_id: str, row: ContactInput, country: str, now: datetime
) -> Contact:
    return Contact(
        account_id=account_id,
        cf1=checked_custom(row.cf1),
        cf2=checked_custom(row.cf2),
        cf3=checked_custom(row.cf3),
        cf4=checked_custom(row.cf4),
        email=checked_email(row.email),
        first_name=checked_name(row.first_name, FIRST_NAME_LENGTH),
        last_name=checked_name(row.last_name, LAST_NAME_LENGTH),
        list_id=list_id,
        mobile=normalise(row.mobile, country),
        updated_at=now,
    )


def opted_out_entry(account_id: str, list_id: str, mobile: E164, now: datetime) -> Contact:
    return Contact(account_id=account_id, list_id=list_id, mobile=mobile, updated_at=now)


def has_room(contact_list: ContactList, fresh: int) -> bool:
    if contact_list.kind is ListKind.OPT_OUT:
        return True
    return contact_list.contact_count + fresh <= LIST_CEILING


def matches(contact: Contact, needle: str, lowered: str) -> bool:
    if contact.mobile.startswith(needle):
        return True
    return lowered in f"{contact.first_name} {contact.last_name}".casefold()


def matching(contacts: Iterable[Contact], needle: str) -> Iterator[Contact]:
    lowered = needle.casefold()
    return (contact for contact in contacts if matches(contact, needle, lowered))


def full_name_of(contact: Contact) -> str:
    return f"{contact.first_name} {contact.last_name}".strip()


def named(lists: Sequence[ContactList], name: str, besides: str) -> bool:
    lowered = name.casefold()
    return any(one.name.casefold() == lowered and one.list_id != besides for one in lists)


def import_message(imported: int, updated: int, skipped: int) -> str:
    return f"Imported {imported}, updated {updated}, skipped {skipped} invalid"


def contacts_counted(count: int) -> str:
    return f"{count} contact" if count == 1 else f"{count} contacts"


def moved_message(moved: int) -> str:
    return f"Moved {contacts_counted(moved)} to the opt-out list"


def removed_message(removed: int) -> str:
    return f"Removed {contacts_counted(removed)}"


def remember(cache: dict[str, str], account_id: str, list_id: str) -> None:
    if len(cache) >= OPT_OUT_CACHE_SIZE:
        cache.pop(next(iter(cache)))
    cache[account_id] = list_id


def csv_line(values: Sequence[str]) -> str:
    buffer = io.StringIO()
    csv.writer(buffer, lineterminator="\n").writerow(values)
    return buffer.getvalue()


@dataclass(frozen=True, slots=True)
class ContactsService:
    clock: Clock
    owners: OwnerLookup
    repo: ContactsRepo
    settings: Settings
    opt_out_ids: dict[str, str] = field(default_factory=dict)

    async def provision_defaults(self, account_id: str, now: datetime) -> None:
        if await self.repo.list_lists(account_id):
            return

        example = ContactList(created_at=now, list_id=new_id(), name=EXAMPLE_LIST)
        opt_out = ContactList(
            created_at=now, kind=ListKind.OPT_OUT, list_id=new_id(), name=OPT_OUT_LIST
        )
        if not await self.repo.put_defaults_if_absent(account_id, example, opt_out):
            return

        owner = await self.owners.owner_of(account_id)
        mobile = normalised_or_none(owner.mobile or "", DEFAULT_COUNTRY)
        if mobile is None:
            return

        await self.repo.upsert_contact(
            Contact(
                account_id=account_id,
                email=owner.email,
                first_name=owner.first_name,
                last_name=owner.last_name,
                list_id=example.list_id,
                mobile=mobile,
                updated_at=now,
            )
        )

    async def opt_outs(self, account_id: str) -> frozenset[E164]:
        opt_out_id = await self._opt_out_id(account_id)
        if opt_out_id is None:
            return frozenset()

        return frozenset(one.mobile for one in await self.repo.all_contacts(opt_out_id))

    async def is_opted_out(self, account_id: str, destination: E164) -> bool:
        opt_out_id = await self._opt_out_id(account_id)
        if opt_out_id is None:
            return False

        return await self.repo.get_contact(opt_out_id, destination) is not None

    async def opt_out(self, account_id: str, mobile: E164, now: datetime) -> None:
        opt_out_id = await self._opt_out_id(account_id)
        if opt_out_id is None:
            raise Internal(OPT_OUT_LIST_MISSING)

        await self.repo.upsert_contact(opted_out_entry(account_id, opt_out_id, mobile, now))

    async def recipients_of(self, account_id: str, list_id: str) -> list[Recipient]:
        await self._list(account_id, list_id)

        contacts = await self.repo.all_contacts(list_id)
        unique = {contact.mobile: contact for contact in contacts}
        return [recipient_of(contact) for contact in unique.values()]

    async def names_of(self, account_id: str, peers: Sequence[E164]) -> dict[E164, str]:
        found = {}
        for peer in peers:
            matches = await self.repo.contacts_with_mobile(account_id, peer)
            name = full_name_of(matches[0]) if matches else None
            if name:
                found[peer] = name
        return found

    async def search(self, account_id: str, q: str, limit: int) -> list[ContactHit]:
        needle = q.strip()
        if not needle:
            return []

        wanted = min(max(limit, 1), SEARCH_LIMIT)
        lists = await self.repo.list_lists(account_id)
        searchable = [one for one in lists if one.kind is not ListKind.OPT_OUT]
        held_by = {one.list_id for one in searchable}

        exact = await self._exact(account_id, needle)
        hits = {one.mobile: hit_of(one) for one in exact if one.list_id in held_by}

        for contact_list in searchable:
            if len(hits) >= wanted:
                break

            page = await self.repo.list_contacts(contact_list.list_id, None, SEARCH_SCAN)
            for contact in matching(page.items, needle):
                hits.setdefault(contact.mobile, hit_of(contact))

        return list(hits.values())[:wanted]

    async def lists(self, account_id: str, q: str | None) -> list[ContactList]:
        lists = await self.repo.list_lists(account_id)
        needle = (q or "").strip().casefold()
        if not needle:
            return lists

        return [one for one in lists if needle in one.name.casefold()]

    async def create_list(self, account_id: str, request: ListRequest) -> ContactList:
        name = checked_list_name(request.name)
        if named(await self.repo.list_lists(account_id), name, ""):
            raise Conflict(DUPLICATE_LIST_NAME)

        created = ContactList(created_at=self.clock(), list_id=new_id(), name=name)
        if not await self.repo.put_list(account_id, created):
            raise Internal(f"list {created.list_id} already exists")

        return created

    async def rename_list(self, account_id: str, list_id: str, request: ListRequest) -> ContactList:
        name = checked_list_name(request.name)
        lists = await self.repo.list_lists(account_id)

        current = next((one for one in lists if one.list_id == list_id), None)
        if current is None:
            raise NotFound(LIST_NOT_FOUND)
        if current.kind is ListKind.OPT_OUT:
            raise Conflict(OPT_OUT_NOT_RENAMABLE)
        if named(lists, name, list_id):
            raise Conflict(DUPLICATE_LIST_NAME)

        if not await self.repo.rename_list(account_id, list_id, name):
            raise NotFound(LIST_NOT_FOUND)

        return current.model_copy(update={"name": name})

    async def delete_list(self, account_id: str, list_id: str) -> None:
        contact_list = await self._list(account_id, list_id)
        if contact_list.kind is ListKind.OPT_OUT:
            raise Conflict(OPT_OUT_NOT_DELETABLE)

        contacts = await self.repo.all_contacts(list_id)
        if contacts:
            await self.repo.delete_contacts(list_id, [one.mobile for one in contacts])

        if not await self.repo.delete_list(account_id, list_id):
            raise NotFound(LIST_NOT_FOUND)

    async def contacts(
        self, account_id: str, list_id: str, q: str | None, cursor: str | None, limit: int
    ) -> ContactPage:
        await self._list(account_id, list_id)

        wanted = min(max(limit, 1), MAX_PAGE_SIZE)
        needle = (q or "").strip()
        if not needle:
            return await self.repo.list_contacts(list_id, cursor, wanted)

        page = await self.repo.list_contacts(list_id, cursor, SEARCH_SCAN)
        found = list(matching(page.items, needle))
        return ContactPage(cursor=page.cursor, items=found[:wanted])

    async def add_contact(self, account_id: str, list_id: str, request: ContactInput) -> Contact:
        contact_list = await self._list(account_id, list_id)
        country = await self._country(account_id)

        contact = contact_of(account_id, list_id, request, country, self.clock())
        await self._store(contact_list, contact)
        return contact

    async def update_contact(
        self, account_id: str, list_id: str, contact_id: str, request: ContactInput
    ) -> Contact:
        contact_list = await self._list(account_id, list_id)
        existing = await self.repo.get_contact(list_id, E164(contact_id))
        if existing is None:
            raise NotFound(CONTACT_NOT_FOUND)

        country = await self._country(account_id)
        contact = contact_of(account_id, list_id, request, country, self.clock())
        await self._store(contact_list, contact)

        if contact.mobile != existing.mobile:
            await self.repo.delete_contact(account_id, list_id, existing.mobile)

        return contact

    async def remove_contact(self, account_id: str, list_id: str, contact_id: str) -> None:
        await self._list(account_id, list_id)

        if not await self.repo.delete_contact(account_id, list_id, E164(contact_id)):
            raise NotFound(CONTACT_NOT_FOUND)

    async def import_contacts(
        self, account_id: str, list_id: str, request: ImportRequest
    ) -> ImportReport:
        if len(request.rows) > IMPORT_CEILING:
            raise BadRequest(TOO_MANY_ROWS)

        contact_list = await self._list(account_id, list_id)
        country = await self._country(account_id)
        now = self.clock()

        parsed: dict[E164, Contact] = {}
        skipped = 0
        for row in request.rows:
            contact = self._parsed_row(account_id, list_id, row, country, now)
            if contact is None:
                skipped += 1
            else:
                parsed[contact.mobile] = contact

        imported = await self._add_many(account_id, contact_list, list(parsed.values()))
        return ImportReport(
            imported=imported,
            message=import_message(imported, len(parsed) - imported, skipped),
            skipped=skipped,
            updated=len(parsed) - imported,
        )

    async def bulk(self, account_id: str, list_id: str, request: BulkRequest) -> ActionResult:
        if len(request.contact_ids) > MAX_BULK:
            raise BadRequest(TOO_MANY_IDS)

        contact_list = await self._list(account_id, list_id)
        wanted = [E164(one) for one in request.contact_ids]
        present = await self.repo.existing_mobiles(list_id, wanted)
        mobiles = [one for one in dict.fromkeys(wanted) if one in present]

        match request.action:
            case BulkAction.DELETE:
                removed = await self._remove_many(account_id, list_id, mobiles)
                return ActionResult(message=removed_message(removed), removed=removed)
            case BulkAction.OPT_OUT:
                moved = await self._move_to_opt_out(account_id, contact_list, mobiles)
                return ActionResult(message=moved_message(moved), removed=moved)
            case _ as unreachable:
                assert_never(unreachable)

    async def clean_up(
        self, account_id: str, list_id: str, request: CleanUpRequest
    ) -> ActionResult:
        contact_list = await self._list(account_id, list_id)
        if contact_list.kind is ListKind.OPT_OUT:
            raise Conflict(OPT_OUT_NOT_CLEANABLE)

        contacts = await self.repo.all_contacts(list_id)
        doomed = await self._doomed(account_id, contacts, request.action)

        removed = await self._remove_many(account_id, list_id, doomed)
        return ActionResult(message=removed_message(removed), removed=removed)

    async def export(self, account_id: str, list_id: str) -> str:
        await self._list(account_id, list_id)

        contacts = await self.repo.all_contacts(list_id)
        rows = [csv_line(EXPORT_COLUMNS)]
        rows.extend(csv_line(export_row(contact)) for contact in contacts)
        return "".join(rows)

    async def _exact(self, account_id: str, needle: str) -> list[Contact]:
        mobile = normalised_or_none(needle, await self._country(account_id))
        if mobile is None:
            return []

        return await self.repo.contacts_with_mobile(account_id, mobile)

    async def _doomed(
        self, account_id: str, contacts: Sequence[Contact], action: CleanUpAction
    ) -> list[E164]:
        match action:
            case CleanUpAction.INVALID:
                country = await self._country(account_id)
                return [
                    one.mobile
                    for one in contacts
                    if normalised_or_none(one.mobile, country) != one.mobile
                ]
            case CleanUpAction.OPTED_OUT:
                opted_out = await self.opt_outs(account_id)
                return [one.mobile for one in contacts if one.mobile in opted_out]
            case _ as unreachable:
                assert_never(unreachable)

    def _parsed_row(
        self, account_id: str, list_id: str, row: ContactInput, country: str, now: datetime
    ) -> Contact | None:
        try:
            return contact_of(account_id, list_id, row, country, now)
        except BadRequest:
            return None

    async def _store(self, contact_list: ContactList, contact: Contact) -> None:
        if not has_room(contact_list, 1):
            existing = await self.repo.get_contact(contact.list_id, contact.mobile)
            if existing is None:
                raise BadRequest(LIST_FULL)

        await self.repo.upsert_contact(contact)

    async def _add_many(
        self, account_id: str, target: ContactList, contacts: Sequence[Contact]
    ) -> int:
        if not contacts:
            return 0

        existing = await self.repo.existing_mobiles(
            target.list_id, [one.mobile for one in contacts]
        )
        fresh = [one for one in contacts if one.mobile not in existing]
        if not has_room(target, len(fresh)):
            raise BadRequest(LIST_FULL)

        await self.repo.put_contacts(contacts)
        if fresh:
            await self.repo.add_count(account_id, target.list_id, len(fresh))

        return len(fresh)

    async def _remove_many(self, account_id: str, list_id: str, mobiles: Sequence[E164]) -> int:
        if not mobiles:
            return 0

        await self.repo.delete_contacts(list_id, mobiles)
        await self.repo.add_count(account_id, list_id, -len(mobiles))
        return len(mobiles)

    async def _move_to_opt_out(
        self, account_id: str, source: ContactList, mobiles: Sequence[E164]
    ) -> int:
        opt_out_id = await self._opt_out_id(account_id)
        if opt_out_id is None:
            raise Internal(OPT_OUT_LIST_MISSING)
        if opt_out_id == source.list_id:
            return 0

        opt_out = await self._list(account_id, opt_out_id)
        now = self.clock()
        entries = [opted_out_entry(account_id, opt_out.list_id, mobile, now) for mobile in mobiles]
        await self._add_many(account_id, opt_out, entries)
        return await self._remove_many(account_id, source.list_id, mobiles)

    async def _opt_out_id(self, account_id: str) -> str | None:
        if (cached := self.opt_out_ids.get(account_id)) is not None:
            return cached

        lists = await self.repo.list_lists(account_id)
        found = next((one for one in lists if one.kind is ListKind.OPT_OUT), None)
        if found is None:
            return None

        remember(self.opt_out_ids, account_id, found.list_id)
        return found.list_id

    async def _list(self, account_id: str, list_id: str) -> ContactList:
        contact_list = await self.repo.get_list(account_id, list_id)
        if contact_list is None:
            raise NotFound(LIST_NOT_FOUND)

        return contact_list

    async def _country(self, account_id: str) -> str:
        return (await self.settings.messaging_settings(account_id)).default_country

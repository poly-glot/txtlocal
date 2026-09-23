from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from txtlocal.shared.phone import E164
from txtlocal.slices.contacts.model import Contact, ContactList, ContactPage
from txtlocal.slices.identity.model import MessagingSettings

ACCOUNT = "account-1"
OTHER_ACCOUNT = "account-2"
NOW = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
OWNER_EMAIL = "demo@txtlocal.local"
OWNER_MOBILE = "+447411972333"
SECOND_MOBILE = "+447411972300"
THIRD_MOBILE = "+447411972111"
US_MOBILE = "+12025550123"


def contact_of(
    list_id: str,
    mobile: str,
    first_name: str = "",
    last_name: str = "",
    account_id: str = ACCOUNT,
) -> Contact:
    return Contact(
        account_id=account_id,
        first_name=first_name,
        last_name=last_name,
        list_id=list_id,
        mobile=E164(mobile),
        updated_at=NOW,
    )


@dataclass
class StubOwner:
    email: str = OWNER_EMAIL
    first_name: str = "Sam"
    last_name: str = "Jones"
    mobile: str | None = OWNER_MOBILE


@dataclass
class StubOwners:
    by_account: dict[str, StubOwner] = field(default_factory=lambda: {ACCOUNT: StubOwner()})

    async def owner_of(self, account_id: str) -> StubOwner:
        return self.by_account[account_id]


@dataclass
class StubSettings:
    by_account: dict[str, MessagingSettings] = field(
        default_factory=lambda: {ACCOUNT: MessagingSettings()}
    )

    async def messaging_settings(self, account_id: str) -> MessagingSettings:
        return self.by_account[account_id]


@dataclass
class InMemoryContactsRepo:
    contacts: dict[tuple[str, E164], Contact] = field(default_factory=dict)
    list_queries: int = 0
    lists: dict[tuple[str, str], ContactList] = field(default_factory=dict)

    async def add_count(self, account_id: str, list_id: str, delta: int) -> bool:
        current = self.lists.get((account_id, list_id))
        if current is None:
            return False

        self.lists[(account_id, list_id)] = current.model_copy(
            update={"contact_count": current.contact_count + delta}
        )
        return True

    async def all_contacts(self, list_id: str) -> list[Contact]:
        held = [one for (owner, _), one in self.contacts.items() if owner == list_id]
        return sorted(held, key=lambda one: one.mobile)

    async def contacts_with_mobile(self, account_id: str, mobile: E164) -> list[Contact]:
        owned = {list_id for (owner, list_id) in self.lists if owner == account_id}
        found = [
            one
            for (list_id, held), one in self.contacts.items()
            if held == mobile and list_id in owned
        ]
        return sorted(found, key=lambda one: one.list_id)

    async def delete_contact(self, account_id: str, list_id: str, mobile: E164) -> bool:
        if self.contacts.pop((list_id, mobile), None) is None:
            return False

        await self.add_count(account_id, list_id, -1)
        return True

    async def delete_contacts(self, list_id: str, mobiles: Sequence[E164]) -> None:
        for mobile in mobiles:
            self.contacts.pop((list_id, mobile), None)

    async def delete_list(self, account_id: str, list_id: str) -> bool:
        return self.lists.pop((account_id, list_id), None) is not None

    async def existing_mobiles(self, list_id: str, mobiles: Sequence[E164]) -> frozenset[E164]:
        return frozenset(one for one in mobiles if (list_id, one) in self.contacts)

    async def get_contact(self, list_id: str, mobile: E164) -> Contact | None:
        return self.contacts.get((list_id, mobile))

    async def get_list(self, account_id: str, list_id: str) -> ContactList | None:
        return self.lists.get((account_id, list_id))

    async def list_contacts(self, list_id: str, cursor: str | None, limit: int) -> ContactPage:
        rows = await self.all_contacts(list_id)
        after = [one for one in rows if cursor is None or one.mobile > cursor]

        page = after[:limit]
        filled = len(page) == limit
        return ContactPage(cursor=page[-1].mobile if filled else None, items=page)

    async def list_lists(self, account_id: str) -> list[ContactList]:
        self.list_queries += 1

        owned = [one for (owner, _), one in self.lists.items() if owner == account_id]
        return sorted(owned, key=lambda one: one.list_id)

    async def put_contacts(self, contacts: Sequence[Contact]) -> None:
        for contact in contacts:
            self.contacts[(contact.list_id, contact.mobile)] = contact

    async def put_defaults_if_absent(
        self, account_id: str, standard: ContactList, opt_out: ContactList
    ) -> bool:
        keys = [(account_id, one.list_id) for one in (standard, opt_out)]
        if any(one in self.lists for one in keys):
            return False

        self.lists[keys[0]] = standard
        self.lists[keys[1]] = opt_out
        return True

    async def put_list(self, account_id: str, contact_list: ContactList) -> bool:
        if (account_id, contact_list.list_id) in self.lists:
            return False

        self.lists[(account_id, contact_list.list_id)] = contact_list
        return True

    async def rename_list(self, account_id: str, list_id: str, name: str) -> bool:
        current = self.lists.get((account_id, list_id))
        if current is None:
            return False

        self.lists[(account_id, list_id)] = current.model_copy(update={"name": name})
        return True

    async def upsert_contact(self, contact: Contact) -> bool:
        held = (contact.list_id, contact.mobile)
        inserted = held not in self.contacts

        self.contacts[held] = contact
        if inserted:
            await self.add_count(contact.account_id, contact.list_id, 1)

        return inserted

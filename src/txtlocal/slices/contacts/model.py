from enum import StrEnum

from txtlocal.shared.model import Model, Rfc3339
from txtlocal.shared.phone import E164

CUSTOM_FIELDS = ("cf1", "cf2", "cf3", "cf4")
EXPORT_COLUMNS = ("mobile", "first_name", "last_name", "email", *CUSTOM_FIELDS)


class BulkAction(StrEnum):
    DELETE = "DELETE"
    OPT_OUT = "OPT_OUT"


class CleanUpAction(StrEnum):
    INVALID = "INVALID"
    OPTED_OUT = "OPTED_OUT"


class ListKind(StrEnum):
    OPT_OUT = "OPT_OUT"
    STANDARD = "STANDARD"


class ContactList(Model):
    contact_count: int = 0
    created_at: Rfc3339
    kind: ListKind = ListKind.STANDARD
    list_id: str
    name: str


class Contact(Model):
    account_id: str
    cf1: str = ""
    cf2: str = ""
    cf3: str = ""
    cf4: str = ""
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    list_id: str
    mobile: E164
    updated_at: Rfc3339


class ContactInput(Model):
    cf1: str = ""
    cf2: str = ""
    cf3: str = ""
    cf4: str = ""
    email: str = ""
    first_name: str = ""
    last_name: str = ""
    mobile: str


class ListRequest(Model):
    name: str


class ImportRequest(Model):
    rows: list[ContactInput]


class BulkRequest(Model):
    action: BulkAction
    contact_ids: list[str]


class CleanUpRequest(Model):
    action: CleanUpAction


class ContactPage(Model):
    cursor: str | None = None
    items: list[Contact]


class ActionResult(Model):
    message: str
    removed: int


class ImportReport(Model):
    imported: int
    message: str
    skipped: int
    updated: int


class ContactHit(Model):
    first_name: str
    last_name: str
    list_id: str
    mobile: E164


class Recipient(Model):
    contact_id: str
    fields: dict[str, str]
    mobile: str


def fields_of(contact: Contact) -> dict[str, str]:
    return {
        "cf1": contact.cf1,
        "cf2": contact.cf2,
        "cf3": contact.cf3,
        "cf4": contact.cf4,
        "email": contact.email,
        "first_name": contact.first_name,
        "last_name": contact.last_name,
        "mobile": contact.mobile,
    }


def recipient_of(contact: Contact) -> Recipient:
    return Recipient(contact_id=contact.mobile, fields=fields_of(contact), mobile=contact.mobile)


def hit_of(contact: Contact) -> ContactHit:
    return ContactHit(
        first_name=contact.first_name,
        last_name=contact.last_name,
        list_id=contact.list_id,
        mobile=contact.mobile,
    )


def export_row(contact: Contact) -> tuple[str, ...]:
    return (
        contact.mobile,
        contact.first_name,
        contact.last_name,
        contact.email,
        contact.cf1,
        contact.cf2,
        contact.cf3,
        contact.cf4,
    )

import asyncio
import itertools
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, cast

from txtlocal.shared.errors import Internal
from txtlocal.shared.model import get_model, model_of
from txtlocal.shared.phone import E164
from txtlocal.shared.table import (
    BY_PREFIX,
    IF_PRESENT,
    UNSUPPORTED_ATTRIBUTE,
    Table,
    backoff,
    condition_failed_as_false,
    delete_if_present,
    key,
    n,
    paged_items,
    partition,
    plain,
    s,
)
from txtlocal.slices.contacts.model import Contact, ContactList, ContactPage

if TYPE_CHECKING:
    from types_aiobotocore_dynamodb.type_defs import (
        AttributeValueTypeDef,
        QueryInputTypeDef,
        TransactWriteItemTypeDef,
        WriteRequestTypeDef,
    )

    from txtlocal.shared.model import Model

ACCOUNT = "ACCOUNT"
BATCH_GET_SIZE = 100
BATCH_WRITE_SIZE = 25
CONTACT_PREFIX = "CONTACT#"
LIST = "LIST"
LIST_PREFIX = "LIST#"
MOBILE_INFIX = "#MOBILE#"
PAGE_CAP = 12
PAGE_CAP_EXCEEDED = "the list read more pages than its cap"
RETRY_ATTEMPTS = 5
UNPROCESSED = "the batch left items unprocessed after every retry"

ADD_COUNT = "ADD contactCount :delta"
BY_MOBILE = "GSI1PK = :pk"
IF_ABSENT = "attribute_not_exists(PK)"
MOBILE_INDEX = "GSI1"
SET_NAME = "SET #name = :name"
NAME_ATTRIBUTE = {"#name": "name"}
SORT_KEY_ONLY = "#sk"
SORT_KEY_ATTRIBUTE = {"#sk": "SK"}


class ContactsRepo(Protocol):
    async def add_count(self, account_id: str, list_id: str, delta: int) -> bool: ...

    async def all_contacts(self, list_id: str) -> list[Contact]: ...

    async def contacts_with_mobile(self, account_id: str, mobile: E164) -> list[Contact]: ...

    async def delete_contact(self, account_id: str, list_id: str, mobile: E164) -> bool: ...

    async def delete_contacts(self, list_id: str, mobiles: Sequence[E164]) -> None: ...

    async def delete_list(self, account_id: str, list_id: str) -> bool: ...

    async def existing_mobiles(self, list_id: str, mobiles: Sequence[E164]) -> frozenset[E164]: ...

    async def get_contact(self, list_id: str, mobile: E164) -> Contact | None: ...

    async def get_list(self, account_id: str, list_id: str) -> ContactList | None: ...

    async def list_contacts(self, list_id: str, cursor: str | None, limit: int) -> ContactPage: ...

    async def list_lists(self, account_id: str) -> list[ContactList]: ...

    async def put_contacts(self, contacts: Sequence[Contact]) -> None: ...

    async def put_defaults_if_absent(
        self, account_id: str, standard: ContactList, opt_out: ContactList
    ) -> bool: ...

    async def put_list(self, account_id: str, contact_list: ContactList) -> bool: ...

    async def rename_list(self, account_id: str, list_id: str, name: str) -> bool: ...

    async def upsert_contact(self, contact: Contact) -> bool: ...


def list_key(account_id: str, list_id: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(ACCOUNT, account_id), f"{LIST_PREFIX}{list_id}")


def contact_key(list_id: str, mobile: E164) -> dict[str, AttributeValueTypeDef]:
    return key(partition(LIST, list_id), f"{CONTACT_PREFIX}{mobile}")


def mobile_partition(account_id: str, mobile: E164) -> str:
    return partition(ACCOUNT, f"{account_id}{MOBILE_INFIX}{mobile}")


def attribute(value: object) -> AttributeValueTypeDef:
    match value:
        case bool():
            return {"BOOL": value}
        case int():
            return {"N": str(value)}
        case str():
            return {"S": value}
    raise Internal(UNSUPPORTED_ATTRIBUTE)


def item_of(
    model: Model, item_key: dict[str, AttributeValueTypeDef]
) -> dict[str, AttributeValueTypeDef]:
    fields = model.model_dump(by_alias=True, exclude_none=True, mode="json")
    return item_key | {name: attribute(value) for name, value in fields.items()}


def contact_item(contact: Contact) -> dict[str, AttributeValueTypeDef]:
    item = item_of(contact, contact_key(contact.list_id, contact.mobile))
    return item | {
        "GSI1PK": s(mobile_partition(contact.account_id, contact.mobile)),
        "GSI1SK": s(f"{LIST_PREFIX}{contact.list_id}"),
    }


def unique(mobiles: Iterable[E164]) -> list[E164]:
    return list(dict.fromkeys(mobiles))


@dataclass(frozen=True, slots=True)
class ContactsDynamoRepo:
    table: Table

    async def add_count(self, account_id: str, list_id: str, delta: int) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeValues={":delta": n(delta)},
            Key=list_key(account_id, list_id),
            TableName=self.table.name,
            UpdateExpression=ADD_COUNT,
        )

    async def all_contacts(self, list_id: str) -> list[Contact]:
        request: QueryInputTypeDef = {
            "ExpressionAttributeValues": {
                ":pk": s(partition(LIST, list_id)),
                ":prefix": s(CONTACT_PREFIX),
            },
            "KeyConditionExpression": BY_PREFIX,
            "TableName": self.table.name,
        }

        items = await paged_items(self.table.client, request, PAGE_CAP, PAGE_CAP_EXCEEDED)
        return [model_of(Contact, item) for item in items]

    async def contacts_with_mobile(self, account_id: str, mobile: E164) -> list[Contact]:
        response = await self.table.client.query(
            ExpressionAttributeValues={":pk": s(mobile_partition(account_id, mobile))},
            IndexName=MOBILE_INDEX,
            KeyConditionExpression=BY_MOBILE,
            TableName=self.table.name,
        )
        return [model_of(Contact, item) for item in response.get("Items", [])]

    async def delete_contact(self, account_id: str, list_id: str, mobile: E164) -> bool:
        return await condition_failed_as_false(self.table.client.transact_write_items)(
            TransactItems=[
                {
                    "Delete": {
                        "ConditionExpression": IF_PRESENT,
                        "Key": contact_key(list_id, mobile),
                        "TableName": self.table.name,
                    }
                },
                self._count_change(account_id, list_id, -1),
            ]
        )

    async def delete_contacts(self, list_id: str, mobiles: Sequence[E164]) -> None:
        await self._batch_write(
            [{"DeleteRequest": {"Key": contact_key(list_id, mobile)}} for mobile in unique(mobiles)]
        )

    async def delete_list(self, account_id: str, list_id: str) -> bool:
        return await delete_if_present(self.table, list_key(account_id, list_id))

    async def existing_mobiles(self, list_id: str, mobiles: Sequence[E164]) -> frozenset[E164]:
        found: set[E164] = set()
        for chunk in itertools.batched(unique(mobiles), BATCH_GET_SIZE, strict=False):
            keys = [contact_key(list_id, mobile) for mobile in chunk]
            found.update(await self._batch_get(keys))
        return frozenset(found)

    async def get_contact(self, list_id: str, mobile: E164) -> Contact | None:
        return await get_model(self.table, Contact, contact_key(list_id, mobile))

    async def get_list(self, account_id: str, list_id: str) -> ContactList | None:
        return await get_model(self.table, ContactList, list_key(account_id, list_id))

    async def list_contacts(self, list_id: str, cursor: str | None, limit: int) -> ContactPage:
        pk = partition(LIST, list_id)
        request: QueryInputTypeDef = {
            "ExpressionAttributeValues": {":pk": s(pk), ":prefix": s(CONTACT_PREFIX)},
            "KeyConditionExpression": BY_PREFIX,
            "Limit": limit,
            "TableName": self.table.name,
        }
        if cursor is not None:
            request["ExclusiveStartKey"] = key(pk, f"{CONTACT_PREFIX}{cursor}")

        response = await self.table.client.query(**request)
        items = [model_of(Contact, item) for item in response.get("Items", [])]
        last = items[-1].mobile if items and "LastEvaluatedKey" in response else None
        return ContactPage(cursor=last, items=items)

    async def list_lists(self, account_id: str) -> list[ContactList]:
        request: QueryInputTypeDef = {
            "ExpressionAttributeValues": {
                ":pk": s(partition(ACCOUNT, account_id)),
                ":prefix": s(LIST_PREFIX),
            },
            "KeyConditionExpression": BY_PREFIX,
            "TableName": self.table.name,
        }

        items = await paged_items(self.table.client, request, PAGE_CAP, PAGE_CAP_EXCEEDED)
        return [model_of(ContactList, item) for item in items]

    async def put_contacts(self, contacts: Sequence[Contact]) -> None:
        await self._batch_write(
            [{"PutRequest": {"Item": contact_item(contact)}} for contact in contacts]
        )

    async def put_defaults_if_absent(
        self, account_id: str, standard: ContactList, opt_out: ContactList
    ) -> bool:
        return await condition_failed_as_false(self.table.client.transact_write_items)(
            TransactItems=[
                self._put_if_absent(item_of(one, list_key(account_id, one.list_id)))
                for one in (standard, opt_out)
            ]
        )

    async def put_list(self, account_id: str, contact_list: ContactList) -> bool:
        return await condition_failed_as_false(self.table.client.put_item)(
            ConditionExpression=IF_ABSENT,
            Item=item_of(contact_list, list_key(account_id, contact_list.list_id)),
            TableName=self.table.name,
        )

    async def rename_list(self, account_id: str, list_id: str, name: str) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeNames=NAME_ATTRIBUTE,
            ExpressionAttributeValues={":name": s(name)},
            Key=list_key(account_id, list_id),
            TableName=self.table.name,
            UpdateExpression=SET_NAME,
        )

    async def upsert_contact(self, contact: Contact) -> bool:
        item = contact_item(contact)
        inserted = await condition_failed_as_false(self.table.client.transact_write_items)(
            TransactItems=[
                self._put_if_absent(item),
                self._count_change(contact.account_id, contact.list_id, 1),
            ]
        )
        if inserted:
            return True

        await self.table.client.put_item(Item=item, TableName=self.table.name)
        return False

    def _count_change(self, account_id: str, list_id: str, delta: int) -> TransactWriteItemTypeDef:
        return {
            "Update": {
                "ConditionExpression": IF_PRESENT,
                "ExpressionAttributeValues": {":delta": n(delta)},
                "Key": list_key(account_id, list_id),
                "TableName": self.table.name,
                "UpdateExpression": ADD_COUNT,
            }
        }

    def _put_if_absent(self, item: dict[str, AttributeValueTypeDef]) -> TransactWriteItemTypeDef:
        return {
            "Put": {"ConditionExpression": IF_ABSENT, "Item": item, "TableName": self.table.name}
        }

    async def _batch_get(self, keys: Sequence[dict[str, AttributeValueTypeDef]]) -> set[E164]:
        pending = list(keys)
        found: set[E164] = set()

        for attempt in range(RETRY_ATTEMPTS):
            response = await self.table.client.batch_get_item(
                RequestItems={
                    self.table.name: {
                        "ConsistentRead": True,
                        "ExpressionAttributeNames": SORT_KEY_ATTRIBUTE,
                        "Keys": pending,
                        "ProjectionExpression": SORT_KEY_ONLY,
                    }
                }
            )
            for item in response["Responses"].get(self.table.name, []):
                found.add(E164(str(plain(item["SK"])).removeprefix(CONTACT_PREFIX)))

            unprocessed = response["UnprocessedKeys"].get(self.table.name)
            if unprocessed is None:
                return found

            pending = [dict(one) for one in unprocessed["Keys"]]
            await asyncio.sleep(backoff(attempt))

        raise Internal(UNPROCESSED)

    async def _batch_write(self, requests: Sequence[WriteRequestTypeDef]) -> None:
        for chunk in itertools.batched(requests, BATCH_WRITE_SIZE, strict=False):
            pending = list(chunk)

            for attempt in range(RETRY_ATTEMPTS):
                response = await self.table.client.batch_write_item(
                    RequestItems={self.table.name: pending}
                )
                left = response["UnprocessedItems"].get(self.table.name)
                if not left:
                    break

                pending = cast("list[WriteRequestTypeDef]", left)
                await asyncio.sleep(backoff(attempt))
            else:
                raise Internal(UNPROCESSED)

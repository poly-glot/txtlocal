from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol

from txtlocal.shared.errors import Internal
from txtlocal.shared.table import (
    IF_PRESENT,
    METADATA_SK,
    Table,
    condition_failed_as_false,
    key,
    n,
    partition,
    s,
    sort_ts,
)
from txtlocal.slices.identity.model import (
    Account,
    AccountSettings,
    MessagingSettings,
    SubPointer,
    User,
)

if TYPE_CHECKING:
    from types_aiobotocore_dynamodb.type_defs import (
        AttributeValueTypeDef,
        QueryInputTypeDef,
        TransactWriteItemTypeDef,
    )

    from txtlocal.shared.model import Model

ACCOUNT = "ACCOUNT"
APIKEY = "APIKEY"
GSI1 = "GSI1"
GSI2 = "GSI2"
MAX_USER_PAGES = 4
RATE_LIMIT = "RL"
SUB = "SUB"
USERNAME = "USERNAME"
USER_SK = "USER#"

IF_ABSENT = "attribute_not_exists(PK)"
IF_UNLINKED = "attribute_exists(PK) AND attribute_not_exists(#cognitoSub)"

API_KEY_QUERY = "GSI2PK = :pk"
USERNAME_QUERY = "GSI1PK = :pk AND GSI1SK = :sk"
USERS_QUERY = "PK = :pk AND begins_with(SK, :prefix)"

LINK_USER = "SET #cognitoSub = :sub, #emailVerified = :verified, #status = :status"
LINK_USER_NAMES = {
    "#cognitoSub": "cognitoSub",
    "#emailVerified": "emailVerified",
    "#status": "status",
}
SET_ACCOUNT_SETTINGS = (
    "SET #name = :name, #timezone = :timezone, #settings.#defaultCountry = :country"
)
SET_ACCOUNT_SETTINGS_NAMES = {
    "#defaultCountry": "defaultCountry",
    "#name": "name",
    "#settings": "settings",
    "#timezone": "timezone",
}
SET_MESSAGING_SETTINGS = "SET #settings = :settings"
SET_MESSAGING_SETTINGS_NAMES = {"#settings": "settings"}

COUNT_RATE_LIMIT = "ADD n :one SET #ttl = if_not_exists(#ttl, :ttl)"
RATE_LIMIT_COUNTER_LOST = "the rate limit counter returned nothing"
RATE_LIMIT_MINUTE_FORMAT = "%Y-%m-%dT%H:%M"
RATE_LIMIT_TTL = timedelta(days=2)
TTL_NAME = {"#ttl": "ttl"}


class IdentityRepo(Protocol):
    async def create_account(self, account: Account, owner: User, pointer: SubPointer) -> bool: ...

    async def find_user_by_api_key(self, digest: str) -> User | None: ...

    async def find_user_by_username(self, username: str) -> User | None: ...

    async def get_account(self, account_id: str) -> Account | None: ...

    async def get_pointer(self, sub: str) -> SubPointer | None: ...

    async def get_user(self, account_id: str, user_id: str) -> User | None: ...

    async def link_user(self, user: User, pointer: SubPointer) -> bool: ...

    async def list_users(self, account_id: str) -> list[User]: ...

    async def put_user(self, user: User) -> bool: ...

    async def save_account(self, account: Account) -> bool: ...

    async def save_user(self, user: User) -> bool: ...

    async def set_account_settings(self, account_id: str, settings: AccountSettings) -> bool: ...

    async def set_messaging_settings(
        self, account_id: str, settings: MessagingSettings
    ) -> bool: ...


def attribute_of(value: object) -> AttributeValueTypeDef:
    match value:
        case bool():
            return {"BOOL": value}
        case int():
            return n(value)
        case datetime():
            return s(sort_ts(value))
        case str():
            return s(value)
        case Mapping():
            return {"M": {str(name): attribute_of(item) for name, item in value.items()}}
        case list() | tuple():
            return {"L": [attribute_of(item) for item in value]}
        case _:
            raise Internal(f"unserialisable {type(value).__name__}")


def value_of(attribute: Mapping[str, object]) -> object:
    match attribute:
        case {"S": str(text)}:
            return text
        case {"N": str(number)}:
            return Decimal(number)
        case {"BOOL": bool(flag)}:
            return flag
        case {"M": Mapping() as nested}:
            return {str(name): value_of(item) for name, item in nested.items()}
        case {"L": list(items)}:
            return [value_of(item) for item in items]
        case {"NULL": True}:
            return None
        case _:
            raise Internal("unreadable attribute")


def record_of(item: Mapping[str, Mapping[str, object]]) -> dict[str, object]:
    return {name: value_of(attribute) for name, attribute in item.items()}


def item_of(model: Model, keys: Mapping[str, str]) -> dict[str, AttributeValueTypeDef]:
    item = {
        name: attribute_of(value)
        for name, value in model.model_dump(by_alias=True, exclude_none=True).items()
    }
    item.update({name: s(value) for name, value in keys.items()})
    return item


def account_key(account_id: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(ACCOUNT, account_id), METADATA_SK)


def user_key(account_id: str, user_id: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(ACCOUNT, account_id), f"{USER_SK}{user_id}")


def pointer_key(sub: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(SUB, sub), METADATA_SK)


def rate_limit_key(user_id: str, minute: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(RATE_LIMIT, f"{user_id}#{minute}"), METADATA_SK)


def epoch_seconds(moment: datetime) -> int:
    return int(moment.timestamp())


def parsed_minute(minute: str) -> datetime:
    return datetime.strptime(minute, RATE_LIMIT_MINUTE_FORMAT).replace(tzinfo=UTC)


def account_item(account: Account) -> dict[str, AttributeValueTypeDef]:
    return item_of(account, {"PK": partition(ACCOUNT, account.account_id), "SK": METADATA_SK})


def user_item(user: User) -> dict[str, AttributeValueTypeDef]:
    return item_of(
        user,
        {
            "GSI1PK": partition(USERNAME, user.username),
            "GSI1SK": METADATA_SK,
            "GSI2PK": partition(APIKEY, user.api_key_hash),
            "PK": partition(ACCOUNT, user.account_id),
            "SK": f"{USER_SK}{user.user_id}",
        },
    )


def pointer_item(pointer: SubPointer) -> dict[str, AttributeValueTypeDef]:
    return item_of(pointer, {"PK": partition(SUB, pointer.sub), "SK": METADATA_SK})


def put(
    table: str, item: dict[str, AttributeValueTypeDef], condition: str
) -> TransactWriteItemTypeDef:
    return {"Put": {"ConditionExpression": condition, "Item": item, "TableName": table}}


def first_user(items: list[dict[str, AttributeValueTypeDef]]) -> User | None:
    return User.model_validate(record_of(items[0])) if items else None


@dataclass(frozen=True, slots=True)
class IdentityDynamoRepo:
    table: Table

    async def create_account(self, account: Account, owner: User, pointer: SubPointer) -> bool:
        return await self.transact(
            [
                put(self.table.name, account_item(account), IF_ABSENT),
                put(self.table.name, user_item(owner), IF_ABSENT),
                put(self.table.name, pointer_item(pointer), IF_ABSENT),
            ]
        )

    async def link_user(self, user: User, pointer: SubPointer) -> bool:
        return await self.transact(
            [
                put(self.table.name, pointer_item(pointer), IF_ABSENT),
                {
                    "Update": {
                        "ConditionExpression": IF_UNLINKED,
                        "ExpressionAttributeNames": LINK_USER_NAMES,
                        "ExpressionAttributeValues": {
                            ":status": s(user.status),
                            ":sub": s(pointer.sub),
                            ":verified": {"BOOL": user.email_verified},
                        },
                        "Key": user_key(user.account_id, user.user_id),
                        "TableName": self.table.name,
                        "UpdateExpression": LINK_USER,
                    }
                },
            ]
        )

    async def put_user(self, user: User) -> bool:
        return await self.put_if(user_item(user), IF_ABSENT)

    async def save_account(self, account: Account) -> bool:
        return await self.put_if(account_item(account), IF_PRESENT)

    async def save_user(self, user: User) -> bool:
        return await self.put_if(user_item(user), IF_PRESENT)

    async def set_account_settings(self, account_id: str, settings: AccountSettings) -> bool:
        return await self.update(
            account_key(account_id),
            SET_ACCOUNT_SETTINGS,
            SET_ACCOUNT_SETTINGS_NAMES,
            {
                ":country": s(settings.default_country),
                ":name": s(settings.name),
                ":timezone": s(settings.timezone),
            },
        )

    async def set_messaging_settings(self, account_id: str, settings: MessagingSettings) -> bool:
        return await self.update(
            account_key(account_id),
            SET_MESSAGING_SETTINGS,
            SET_MESSAGING_SETTINGS_NAMES,
            {":settings": attribute_of(settings.model_dump(by_alias=True))},
        )

    async def get_account(self, account_id: str) -> Account | None:
        item = await self.get(account_key(account_id))
        return None if item is None else Account.model_validate(record_of(item))

    async def get_user(self, account_id: str, user_id: str) -> User | None:
        item = await self.get(user_key(account_id, user_id))
        return None if item is None else User.model_validate(record_of(item))

    async def get_pointer(self, sub: str) -> SubPointer | None:
        item = await self.get(pointer_key(sub))
        return None if item is None else SubPointer.model_validate(record_of(item))

    async def find_user_by_username(self, username: str) -> User | None:
        response = await self.table.client.query(
            ExpressionAttributeValues={
                ":pk": s(partition(USERNAME, username)),
                ":sk": s(METADATA_SK),
            },
            IndexName=GSI1,
            KeyConditionExpression=USERNAME_QUERY,
            Limit=1,
            TableName=self.table.name,
        )
        return first_user(response["Items"])

    async def find_user_by_api_key(self, digest: str) -> User | None:
        response = await self.table.client.query(
            ExpressionAttributeValues={":pk": s(partition(APIKEY, digest))},
            IndexName=GSI2,
            KeyConditionExpression=API_KEY_QUERY,
            Limit=1,
            TableName=self.table.name,
        )
        return first_user(response["Items"])

    async def list_users(self, account_id: str) -> list[User]:
        request: QueryInputTypeDef = {
            "ExpressionAttributeValues": {
                ":pk": s(partition(ACCOUNT, account_id)),
                ":prefix": s(USER_SK),
            },
            "KeyConditionExpression": USERS_QUERY,
            "TableName": self.table.name,
        }
        users: list[User] = []

        for _ in range(MAX_USER_PAGES):
            response = await self.table.client.query(**request)
            users.extend(User.model_validate(record_of(item)) for item in response["Items"])

            start = response.get("LastEvaluatedKey")
            if start is None:
                return users
            request["ExclusiveStartKey"] = start

        raise Internal("too many user pages")

    async def get(
        self, item_key: dict[str, AttributeValueTypeDef]
    ) -> dict[str, AttributeValueTypeDef] | None:
        response = await self.table.client.get_item(
            ConsistentRead=True, Key=item_key, TableName=self.table.name
        )
        return response.get("Item")

    @condition_failed_as_false
    async def transact(self, items: list[TransactWriteItemTypeDef]) -> None:
        await self.table.client.transact_write_items(TransactItems=items)

    @condition_failed_as_false
    async def put_if(self, item: dict[str, AttributeValueTypeDef], condition: str) -> None:
        await self.table.client.put_item(
            ConditionExpression=condition, Item=item, TableName=self.table.name
        )

    @condition_failed_as_false
    async def update(
        self,
        item_key: dict[str, AttributeValueTypeDef],
        expression: str,
        names: Mapping[str, str],
        values: Mapping[str, AttributeValueTypeDef],
    ) -> None:
        await self.table.client.update_item(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            Key=item_key,
            TableName=self.table.name,
            UpdateExpression=expression,
        )


@dataclass(frozen=True, slots=True)
class RateLimitsDynamoRepo:
    table: Table

    async def count(self, user_id: str, minute: str) -> int:
        attributes: dict[str, AttributeValueTypeDef] = {}

        async def write() -> None:
            output = await self.table.client.update_item(
                ExpressionAttributeNames=TTL_NAME,
                ExpressionAttributeValues={
                    ":one": n(1),
                    ":ttl": n(epoch_seconds(parsed_minute(minute) + RATE_LIMIT_TTL)),
                },
                Key=rate_limit_key(user_id, minute),
                ReturnValues="UPDATED_NEW",
                TableName=self.table.name,
                UpdateExpression=COUNT_RATE_LIMIT,
            )
            attributes.update(output.get("Attributes", {}))

        await condition_failed_as_false(write)()
        if "n" not in attributes:
            raise Internal(RATE_LIMIT_COUNTER_LOST)
        return int(attributes["n"]["N"])

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from txtlocal.shared.errors import Internal
from txtlocal.shared.model import get_model, model_of
from txtlocal.shared.table import (
    IF_PRESENT,
    METADATA_SK,
    UNSUPPORTED_ATTRIBUTE,
    Table,
    condition_failed_as_false,
    delete_if_present,
    key,
    n,
    paged_items,
    partition,
    prefix_items,
    s,
)
from txtlocal.slices.automation.model import (
    DeliveryReportRule,
    EmailSender,
    InboundRule,
    Website,
    WebsiteStatus,
)

if TYPE_CHECKING:
    from types_aiobotocore_dynamodb.type_defs import AttributeValueTypeDef, QueryInputTypeDef

    from txtlocal.shared.model import Model

ACCOUNT = "ACCOUNT"
ACCOUNT_PREFIX = partition(ACCOUNT, "")
DLRRULE_PREFIX = "DLRRULE#"
EMAILSENDER_PREFIX = "EMAILSENDER#"
GSI1 = "GSI1"
GSI2 = "GSI2"
PAGE_CAP = 4
PAGE_CAP_EXCEEDED = "automation query exceeded the page cap"
RULE_PREFIX = "RULE#"
UNDER_REVIEW_PARTITION = partition("WEBSITES", "UNDER_REVIEW")
WEBSITE_PREFIX = "WEBSITE#"

APPROVE_WEBSITE = "SET #status = :status REMOVE GSI2PK"
BY_EMAIL = "GSI1PK = :pk"
BY_GSI2 = "GSI2PK = :pk"
IF_ABSENT = "attribute_not_exists(PK)"
INCREMENT_VOTE = "SET votes.#kw = if_not_exists(votes.#kw, :zero) + :one"
REJECT_NAMES = {"#reason": "rejectedReason", "#status": "status"}
REJECT_WEBSITE = "SET #status = :status, #reason = :reason REMOVE GSI2PK"
STATUS_NAME = {"#status": "status"}


class AutomationRepo(Protocol):
    async def approve_website(self, account_id: str, domain: str) -> bool: ...

    async def delete_delivery_rule(self, account_id: str, rule_id: str) -> bool: ...

    async def delete_email_sender(self, account_id: str, email: str) -> bool: ...

    async def delete_rule(self, account_id: str, rule_id: str) -> bool: ...

    async def email_senders_by_address(self, email: str) -> list[tuple[str, EmailSender]]: ...

    async def get_delivery_rule(
        self, account_id: str, rule_id: str
    ) -> DeliveryReportRule | None: ...

    async def get_email_sender(self, account_id: str, email: str) -> EmailSender | None: ...

    async def get_rule(self, account_id: str, rule_id: str) -> InboundRule | None: ...

    async def get_website(self, account_id: str, domain: str) -> Website | None: ...

    async def increment_vote(self, account_id: str, rule_id: str, keyword: str) -> bool: ...

    async def list_delivery_rules(self, account_id: str) -> list[DeliveryReportRule]: ...

    async def list_email_senders(self, account_id: str) -> list[EmailSender]: ...

    async def list_rules(self, account_id: str) -> list[InboundRule]: ...

    async def list_websites(self, account_id: str) -> list[Website]: ...

    async def put_delivery_rule(self, account_id: str, rule: DeliveryReportRule) -> None: ...

    async def put_email_sender_if_absent(self, account_id: str, sender: EmailSender) -> bool: ...

    async def put_rule(self, account_id: str, rule: InboundRule) -> None: ...

    async def put_website_if_absent(self, account_id: str, website: Website) -> bool: ...

    async def reject_website(self, account_id: str, domain: str, reason: str) -> bool: ...

    async def replace_delivery_rule(self, account_id: str, rule: DeliveryReportRule) -> bool: ...

    async def replace_rule(self, account_id: str, rule: InboundRule) -> bool: ...

    async def websites_under_review(self) -> list[tuple[str, Website]]: ...


def rule_key(account_id: str, rule_id: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(ACCOUNT, account_id), f"{RULE_PREFIX}{rule_id}")


def delivery_rule_key(account_id: str, rule_id: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(ACCOUNT, account_id), f"{DLRRULE_PREFIX}{rule_id}")


def website_key(account_id: str, domain: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(ACCOUNT, account_id), f"{WEBSITE_PREFIX}{domain}")


def email_sender_key(account_id: str, email: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition(ACCOUNT, account_id), f"{EMAILSENDER_PREFIX}{email}")


def attribute(value: object) -> AttributeValueTypeDef:
    match value:
        case bool():
            return {"BOOL": value}
        case int():
            return {"N": str(value)}
        case str():
            return {"S": value}
        case list():
            return {"L": [attribute(entry) for entry in value]}
        case dict():
            return {"M": {name: attribute(entry) for name, entry in value.items()}}
    raise Internal(UNSUPPORTED_ATTRIBUTE)


def item_of(
    model: Model, item_key: dict[str, AttributeValueTypeDef]
) -> dict[str, AttributeValueTypeDef]:
    fields = model.model_dump(exclude_none=True, mode="json")
    return item_key | {name: attribute(value) for name, value in fields.items()}


def pk_of(item: Mapping[str, AttributeValueTypeDef]) -> str:
    match item["PK"]:
        case {"S": str(text)}:
            return text
    raise Internal(UNSUPPORTED_ATTRIBUTE)


def account_id_of(item: Mapping[str, AttributeValueTypeDef]) -> str:
    return pk_of(item).removeprefix(ACCOUNT_PREFIX)


def website_item(account_id: str, website: Website) -> dict[str, AttributeValueTypeDef]:
    item = item_of(website, website_key(account_id, website.domain))
    if website.status is WebsiteStatus.UNDER_REVIEW:
        return item | {"GSI2PK": s(UNDER_REVIEW_PARTITION)}
    return item


def email_sender_item(account_id: str, sender: EmailSender) -> dict[str, AttributeValueTypeDef]:
    item = item_of(sender, email_sender_key(account_id, sender.email))
    return item | {"GSI1PK": s(partition("EMAILSENDER", sender.email)), "GSI1SK": s(METADATA_SK)}


@dataclass(frozen=True, slots=True)
class AutomationDynamoRepo:
    table: Table

    async def approve_website(self, account_id: str, domain: str) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeNames=STATUS_NAME,
            ExpressionAttributeValues={":status": s(WebsiteStatus.APPROVED)},
            Key=website_key(account_id, domain),
            TableName=self.table.name,
            UpdateExpression=APPROVE_WEBSITE,
        )

    async def delete_delivery_rule(self, account_id: str, rule_id: str) -> bool:
        return await delete_if_present(self.table, delivery_rule_key(account_id, rule_id))

    async def delete_email_sender(self, account_id: str, email: str) -> bool:
        return await delete_if_present(self.table, email_sender_key(account_id, email))

    async def delete_rule(self, account_id: str, rule_id: str) -> bool:
        return await delete_if_present(self.table, rule_key(account_id, rule_id))

    async def email_senders_by_address(self, email: str) -> list[tuple[str, EmailSender]]:
        request: QueryInputTypeDef = {
            "ExpressionAttributeValues": {":pk": s(partition("EMAILSENDER", email))},
            "IndexName": GSI1,
            "KeyConditionExpression": BY_EMAIL,
            "TableName": self.table.name,
        }
        items = await self._paged(request)
        return [(account_id_of(item), model_of(EmailSender, item)) for item in items]

    async def get_delivery_rule(self, account_id: str, rule_id: str) -> DeliveryReportRule | None:
        return await get_model(
            self.table, DeliveryReportRule, delivery_rule_key(account_id, rule_id)
        )

    async def get_email_sender(self, account_id: str, email: str) -> EmailSender | None:
        return await get_model(self.table, EmailSender, email_sender_key(account_id, email))

    async def get_rule(self, account_id: str, rule_id: str) -> InboundRule | None:
        return await get_model(self.table, InboundRule, rule_key(account_id, rule_id))

    async def get_website(self, account_id: str, domain: str) -> Website | None:
        return await get_model(self.table, Website, website_key(account_id, domain))

    async def increment_vote(self, account_id: str, rule_id: str, keyword: str) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeNames={"#kw": keyword},
            ExpressionAttributeValues={":one": n(1), ":zero": n(0)},
            Key=rule_key(account_id, rule_id),
            TableName=self.table.name,
            UpdateExpression=INCREMENT_VOTE,
        )

    async def list_delivery_rules(self, account_id: str) -> list[DeliveryReportRule]:
        items = await self._query(account_id, DLRRULE_PREFIX)
        return [model_of(DeliveryReportRule, item) for item in items]

    async def list_email_senders(self, account_id: str) -> list[EmailSender]:
        items = await self._query(account_id, EMAILSENDER_PREFIX)
        return [model_of(EmailSender, item) for item in items]

    async def list_rules(self, account_id: str) -> list[InboundRule]:
        items = await self._query(account_id, RULE_PREFIX)
        return [model_of(InboundRule, item) for item in items]

    async def list_websites(self, account_id: str) -> list[Website]:
        items = await self._query(account_id, WEBSITE_PREFIX)
        return [model_of(Website, item) for item in items]

    async def put_delivery_rule(self, account_id: str, rule: DeliveryReportRule) -> None:
        await self.table.client.put_item(
            Item=item_of(rule, delivery_rule_key(account_id, rule.rule_id)),
            TableName=self.table.name,
        )

    async def put_email_sender_if_absent(self, account_id: str, sender: EmailSender) -> bool:
        return await condition_failed_as_false(self.table.client.put_item)(
            ConditionExpression=IF_ABSENT,
            Item=email_sender_item(account_id, sender),
            TableName=self.table.name,
        )

    async def put_rule(self, account_id: str, rule: InboundRule) -> None:
        await self.table.client.put_item(
            Item=item_of(rule, rule_key(account_id, rule.rule_id)), TableName=self.table.name
        )

    async def put_website_if_absent(self, account_id: str, website: Website) -> bool:
        return await condition_failed_as_false(self.table.client.put_item)(
            ConditionExpression=IF_ABSENT,
            Item=website_item(account_id, website),
            TableName=self.table.name,
        )

    async def reject_website(self, account_id: str, domain: str, reason: str) -> bool:
        return await condition_failed_as_false(self.table.client.update_item)(
            ConditionExpression=IF_PRESENT,
            ExpressionAttributeNames=REJECT_NAMES,
            ExpressionAttributeValues={":reason": s(reason), ":status": s(WebsiteStatus.REJECTED)},
            Key=website_key(account_id, domain),
            TableName=self.table.name,
            UpdateExpression=REJECT_WEBSITE,
        )

    async def replace_delivery_rule(self, account_id: str, rule: DeliveryReportRule) -> bool:
        return await condition_failed_as_false(self.table.client.put_item)(
            ConditionExpression=IF_PRESENT,
            Item=item_of(rule, delivery_rule_key(account_id, rule.rule_id)),
            TableName=self.table.name,
        )

    async def replace_rule(self, account_id: str, rule: InboundRule) -> bool:
        return await condition_failed_as_false(self.table.client.put_item)(
            ConditionExpression=IF_PRESENT,
            Item=item_of(rule, rule_key(account_id, rule.rule_id)),
            TableName=self.table.name,
        )

    async def websites_under_review(self) -> list[tuple[str, Website]]:
        request: QueryInputTypeDef = {
            "ExpressionAttributeValues": {":pk": s(UNDER_REVIEW_PARTITION)},
            "IndexName": GSI2,
            "KeyConditionExpression": BY_GSI2,
            "TableName": self.table.name,
        }
        items = await self._paged(request)
        return [(account_id_of(item), model_of(Website, item)) for item in items]

    async def _query(self, account_id: str, prefix: str) -> list[dict[str, AttributeValueTypeDef]]:
        return await prefix_items(
            self.table, partition(ACCOUNT, account_id), prefix, PAGE_CAP, PAGE_CAP_EXCEEDED
        )

    async def _paged(self, request: QueryInputTypeDef) -> list[dict[str, AttributeValueTypeDef]]:
        return await paged_items(self.table.client, request, PAGE_CAP, PAGE_CAP_EXCEEDED)

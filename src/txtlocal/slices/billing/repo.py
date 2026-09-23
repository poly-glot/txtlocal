from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol, assert_never
from uuid import UUID

from txtlocal.shared.errors import Internal
from txtlocal.shared.money import Micro
from txtlocal.shared.table import (
    APP,
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
from txtlocal.slices.billing.model import (
    BillingAccount,
    LedgerEntry,
    LedgerKind,
    LedgerOrder,
    Page,
    TopUp,
    TopUpStatus,
)

if TYPE_CHECKING:
    from types_aiobotocore_dynamodb.type_defs import (
        AttributeValueTypeDef,
        QueryInputTypeDef,
        TransactWriteItemTypeDef,
    )

    from txtlocal.shared.model import Model
    from txtlocal.slices.messaging.model import Product

EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
EVENT_TTL = timedelta(days=30)
PAGE_SIZE = 20
PLATFORM = f"{APP}#PLATFORM"
RECHARGE_IN_FLIGHT_TTL = timedelta(hours=1)
RENTAL_EVENT_PREFIX = "RENTAL#"
TRIAL_SK = "0000#TRIAL"
TOPUP_SK_PREFIX = "TOPUP#"

CLEAR_LOW_BALANCE_ALERT = "REMOVE lowBalanceAlertedAt"
CLEAR_RECHARGE_IN_FLIGHT = "REMOVE rechargeInFlight"
CREDIT_BALANCE = "ADD balanceMicro :amount"
CREDIT_RECHARGE = "SET hasToppedUp = :true REMOVE rechargeInFlight ADD balanceMicro :credit"
CREDIT_TOPUP = "SET hasToppedUp = :true ADD balanceMicro :credit"
DEBIT_BALANCE = "SET balanceMicro = balanceMicro - :amount"
DEBIT_IF_COVERED = "balanceMicro >= :amount"
DECLINE_RECHARGE = "SET autoRecharge = :false REMOVE rechargeInFlight"
GRANT_TRIAL = "ADD balanceMicro :amount SET trialEndsAt = :trialEndsAt"
IF_ABSENT = "attribute_not_exists(PK)"
IF_LOW_BALANCE_ALERTED = "attribute_exists(PK) AND attribute_exists(lowBalanceAlertedAt)"
IF_NO_RECHARGE_IN_FLIGHT = (
    "attribute_exists(PK) AND (attribute_not_exists(rechargeInFlight) OR rechargeInFlight < :stale)"
)
IF_NO_STRIPE_CUSTOMER = "attribute_exists(PK) AND attribute_not_exists(stripeCustomerId)"
IF_NOT_LOW_BALANCE_ALERTED = "attribute_exists(PK) AND attribute_not_exists(lowBalanceAlertedAt)"
IF_RECHARGE_IN_FLIGHT = "attribute_exists(PK) AND attribute_exists(rechargeInFlight)"
KIND_IS_TOPUP = "kind = :topup"
MARK_TOPUP_PAID = "SET #status = :paid, invoiceNumber = :num, invoiceUrl = :url"
OWN_PARTITION = "PK = :pk"
SET_BALANCE_MANAGEMENT = (
    "SET alertThresholdMicro = :alertThresholdMicro, autoRecharge = :autoRecharge, "
    "lowBalanceThresholdMicro = :lowBalanceThresholdMicro, "
    "rechargeAmountMicro = :rechargeAmountMicro"
)
SET_LOW_BALANCE_ALERTED = "SET lowBalanceAlertedAt = :now"
SET_RECHARGE_IN_FLIGHT = "SET rechargeInFlight = :now"
SET_STRIPE_CUSTOMER = "SET stripeCustomerId = :id"

REFUND_WITHOUT_REF = "a REFUND ledger entry needs the ref it settles"


class BillingRepo(Protocol):
    async def charge_rental_once(
        self, account_id: str, sender_id: str, period: datetime, entry: LedgerEntry
    ) -> bool: ...

    async def clear_low_balance_alert(self, account_id: str) -> bool: ...

    async def clear_recharge_in_flight(self, account_id: str) -> bool: ...

    async def credit(self, account_id: str, entry: LedgerEntry) -> bool: ...

    async def credit_recharge(
        self, idempotency_key: str, account_id: str, entry: LedgerEntry
    ) -> bool: ...

    async def credit_topup(self, event_id: str, top_up: TopUp, entry: LedgerEntry) -> bool: ...

    async def debit(self, account_id: str, entry: LedgerEntry) -> bool: ...

    async def decline_recharge(
        self, idempotency_key: str, account_id: str, entry: LedgerEntry
    ) -> bool: ...

    async def get_topup(self, account_id: str, top_up_id: str) -> TopUp | None: ...

    async def grant_trial(
        self, account_id: str, entry: LedgerEntry, trial_ends_at: datetime
    ) -> bool: ...

    async def ledger_page(self, account_id: str, cursor: str | None) -> Page[LedgerEntry]: ...

    async def load_account(self, account_id: str) -> BillingAccount | None: ...

    async def put_topup(self, top_up: TopUp) -> bool: ...

    async def rate(self, country: str, product: Product) -> Micro | None: ...

    async def rental_charged(self, sender_id: str, period: datetime) -> bool: ...

    async def save_stripe_customer_id(self, account_id: str, customer_id: str) -> bool: ...

    async def set_low_balance_alerted(self, account_id: str, now: datetime) -> bool: ...

    async def set_recharge_in_flight(self, account_id: str, now: datetime) -> bool: ...

    async def topups_page(
        self, account_id: str, cursor: str | None, order: LedgerOrder
    ) -> Page[LedgerEntry]: ...

    async def update_balance_management(
        self,
        account_id: str,
        *,
        alert_threshold_micro: Micro,
        auto_recharge: bool,
        low_balance_threshold_micro: Micro,
        recharge_amount_micro: Micro,
    ) -> bool: ...


def account_key(account_id: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition("ACCOUNT", account_id), METADATA_SK)


def topup_key(account_id: str, top_up_id: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition("ACCOUNT", account_id), f"{TOPUP_SK_PREFIX}{top_up_id}")


def event_key(event_id: str) -> dict[str, AttributeValueTypeDef]:
    return key(partition("EVENT", event_id), METADATA_SK)


def ledger_partition(account_id: str) -> str:
    return partition("ACCOUNT", f"{account_id}#LEDGER")


def rate_sort_key(country: str, product: Product) -> str:
    return f"RATE#{country}#{product}"


def rental_event_id(sender_id: str, period: datetime) -> str:
    return f"{RENTAL_EVENT_PREFIX}{sender_id}#{sort_ts(period)}"


def minted_at(uuid7_id: str) -> datetime:
    return EPOCH + timedelta(milliseconds=UUID(uuid7_id).time)


def epoch_seconds(moment: datetime) -> int:
    return int(moment.timestamp())


def ledger_sort_key(entry: LedgerEntry) -> str:
    match entry.kind:
        case LedgerKind.TRIAL:
            return TRIAL_SK
        case LedgerKind.REFUND:
            if entry.ref is None:
                raise Internal(REFUND_WITHOUT_REF)
            return f"{sort_ts(minted_at(entry.ref))}#{entry.ref}"
        case LedgerKind.ADJUSTMENT | LedgerKind.RENTAL | LedgerKind.SEND | LedgerKind.TOPUP:
            return f"{sort_ts(entry.created_at)}#{entry.entry_id}"
        case _:
            assert_never(entry.kind)


def attribute_of(value: object) -> AttributeValueTypeDef:
    match value:
        case bool():
            return {"BOOL": value}
        case int():
            return n(value)
        case datetime():
            return s(sort_ts(value))
        case str():
            return s(str(value))
        case _:
            raise TypeError(type(value).__name__)


def to_item(model: Model) -> dict[str, AttributeValueTypeDef]:
    return {
        name: attribute_of(value)
        for name, value in model.model_dump(by_alias=True, exclude_none=True).items()
    }


def from_item(item: Mapping[str, AttributeValueTypeDef]) -> dict[str, object]:
    return {name: next(iter(value.values())) for name, value in item.items()}


def event_put(event_id: str, now: datetime, table_name: str) -> TransactWriteItemTypeDef:
    return {
        "Put": {
            "ConditionExpression": IF_ABSENT,
            "Item": {
                **event_key(event_id),
                "receivedAt": s(sort_ts(now)),
                "ttl": n(epoch_seconds(now + EVENT_TTL)),
            },
            "TableName": table_name,
        }
    }


@dataclass(frozen=True, slots=True)
class BillingDynamoRepo:
    table: Table

    async def credit(self, account_id: str, entry: LedgerEntry) -> bool:
        return await self._transact(
            {
                "Update": {
                    "ConditionExpression": IF_PRESENT,
                    "ExpressionAttributeValues": {":amount": n(entry.amount_micro)},
                    "Key": account_key(account_id),
                    "TableName": self.table.name,
                    "UpdateExpression": CREDIT_BALANCE,
                }
            },
            self._ledger_put(account_id, entry),
        )

    async def debit(self, account_id: str, entry: LedgerEntry) -> bool:
        return await self._transact(
            self._debit_item(account_id, entry), self._ledger_put(account_id, entry)
        )

    async def charge_rental_once(
        self, account_id: str, sender_id: str, period: datetime, entry: LedgerEntry
    ) -> bool:
        return await self._transact(
            event_put(rental_event_id(sender_id, period), entry.created_at, self.table.name),
            self._debit_item(account_id, entry),
            self._ledger_put(account_id, entry),
        )

    async def rental_charged(self, sender_id: str, period: datetime) -> bool:
        response = await self.table.client.get_item(
            ConsistentRead=True,
            Key=event_key(rental_event_id(sender_id, period)),
            TableName=self.table.name,
        )
        return "Item" in response

    async def grant_trial(
        self, account_id: str, entry: LedgerEntry, trial_ends_at: datetime
    ) -> bool:
        return await self._transact(
            {
                "Update": {
                    "ConditionExpression": IF_PRESENT,
                    "ExpressionAttributeValues": {
                        ":amount": n(entry.amount_micro),
                        ":trialEndsAt": s(sort_ts(trial_ends_at)),
                    },
                    "Key": account_key(account_id),
                    "TableName": self.table.name,
                    "UpdateExpression": GRANT_TRIAL,
                }
            },
            self._ledger_put(account_id, entry),
        )

    async def save_stripe_customer_id(self, account_id: str, customer_id: str) -> bool:
        return await self._update(
            account_key(account_id),
            SET_STRIPE_CUSTOMER,
            {":id": s(customer_id)},
            IF_NO_STRIPE_CUSTOMER,
        )

    async def set_recharge_in_flight(self, account_id: str, now: datetime) -> bool:
        return await self._update(
            account_key(account_id),
            SET_RECHARGE_IN_FLIGHT,
            {":now": s(sort_ts(now)), ":stale": s(sort_ts(now - RECHARGE_IN_FLIGHT_TTL))},
            IF_NO_RECHARGE_IN_FLIGHT,
        )

    async def clear_recharge_in_flight(self, account_id: str) -> bool:
        return await self._update(
            account_key(account_id), CLEAR_RECHARGE_IN_FLIGHT, {}, IF_RECHARGE_IN_FLIGHT
        )

    async def set_low_balance_alerted(self, account_id: str, now: datetime) -> bool:
        return await self._update(
            account_key(account_id),
            SET_LOW_BALANCE_ALERTED,
            {":now": s(sort_ts(now))},
            IF_NOT_LOW_BALANCE_ALERTED,
        )

    async def clear_low_balance_alert(self, account_id: str) -> bool:
        return await self._update(
            account_key(account_id), CLEAR_LOW_BALANCE_ALERT, {}, IF_LOW_BALANCE_ALERTED
        )

    async def update_balance_management(
        self,
        account_id: str,
        *,
        alert_threshold_micro: Micro,
        auto_recharge: bool,
        low_balance_threshold_micro: Micro,
        recharge_amount_micro: Micro,
    ) -> bool:
        return await self._update(
            account_key(account_id),
            SET_BALANCE_MANAGEMENT,
            {
                ":alertThresholdMicro": n(alert_threshold_micro),
                ":autoRecharge": {"BOOL": auto_recharge},
                ":lowBalanceThresholdMicro": n(low_balance_threshold_micro),
                ":rechargeAmountMicro": n(recharge_amount_micro),
            },
            IF_PRESENT,
        )

    async def put_topup(self, top_up: TopUp) -> bool:
        return await self._put_if(
            {**topup_key(top_up.account_id, top_up.top_up_id), **to_item(top_up)}, IF_ABSENT
        )

    async def get_topup(self, account_id: str, top_up_id: str) -> TopUp | None:
        response = await self.table.client.get_item(
            ConsistentRead=True, Key=topup_key(account_id, top_up_id), TableName=self.table.name
        )
        item = response.get("Item")
        return None if item is None else TopUp.model_validate(from_item(item))

    async def credit_topup(self, event_id: str, top_up: TopUp, entry: LedgerEntry) -> bool:
        return await self._transact(
            event_put(event_id, entry.created_at, self.table.name),
            {
                "Update": {
                    "ConditionExpression": IF_PRESENT,
                    "ExpressionAttributeValues": {
                        ":credit": n(entry.amount_micro),
                        ":true": {"BOOL": True},
                    },
                    "Key": account_key(top_up.account_id),
                    "TableName": self.table.name,
                    "UpdateExpression": CREDIT_TOPUP,
                }
            },
            self._ledger_put(top_up.account_id, entry),
            {
                "Update": {
                    "ConditionExpression": IF_PRESENT,
                    "ExpressionAttributeNames": {"#status": "status"},
                    "ExpressionAttributeValues": {
                        ":num": s(top_up.invoice_number or ""),
                        ":paid": s(TopUpStatus.PAID),
                        ":url": s(top_up.invoice_url or ""),
                    },
                    "Key": topup_key(top_up.account_id, top_up.top_up_id),
                    "TableName": self.table.name,
                    "UpdateExpression": MARK_TOPUP_PAID,
                }
            },
        )

    async def credit_recharge(
        self, idempotency_key: str, account_id: str, entry: LedgerEntry
    ) -> bool:
        return await self._transact(
            event_put(idempotency_key, entry.created_at, self.table.name),
            {
                "Update": {
                    "ConditionExpression": IF_PRESENT,
                    "ExpressionAttributeValues": {
                        ":credit": n(entry.amount_micro),
                        ":true": {"BOOL": True},
                    },
                    "Key": account_key(account_id),
                    "TableName": self.table.name,
                    "UpdateExpression": CREDIT_RECHARGE,
                }
            },
            self._ledger_put(account_id, entry),
        )

    async def decline_recharge(
        self, idempotency_key: str, account_id: str, entry: LedgerEntry
    ) -> bool:
        return await self._transact(
            event_put(idempotency_key, entry.created_at, self.table.name),
            {
                "Update": {
                    "ConditionExpression": IF_PRESENT,
                    "ExpressionAttributeValues": {":false": {"BOOL": False}},
                    "Key": account_key(account_id),
                    "TableName": self.table.name,
                    "UpdateExpression": DECLINE_RECHARGE,
                }
            },
            self._ledger_put(account_id, entry),
        )

    async def ledger_page(self, account_id: str, cursor: str | None) -> Page[LedgerEntry]:
        rows, next_cursor = await self._ledger_query(account_id, cursor, None, LedgerOrder.DESC)
        return Page[LedgerEntry](items=rows, next_cursor=next_cursor)

    async def topups_page(
        self, account_id: str, cursor: str | None, order: LedgerOrder
    ) -> Page[LedgerEntry]:
        rows, next_cursor = await self._ledger_query(account_id, cursor, KIND_IS_TOPUP, order)
        return Page[LedgerEntry](items=rows, next_cursor=next_cursor)

    async def load_account(self, account_id: str) -> BillingAccount | None:
        response = await self.table.client.get_item(
            ConsistentRead=True, Key=account_key(account_id), TableName=self.table.name
        )
        item = response.get("Item")
        return None if item is None else BillingAccount.model_validate(from_item(item))

    async def rate(self, country: str, product: Product) -> Micro | None:
        response = await self.table.client.get_item(
            Key=key(PLATFORM, rate_sort_key(country, product)), TableName=self.table.name
        )
        item = response.get("Item")
        return None if item is None else Micro(int(item["priceMicro"]["N"]))

    async def _ledger_query(
        self,
        account_id: str,
        cursor: str | None,
        filter_expression: str | None,
        order: LedgerOrder,
    ) -> tuple[list[LedgerEntry], str | None]:
        pk = ledger_partition(account_id)
        values: dict[str, AttributeValueTypeDef] = {":pk": s(pk)}
        if filter_expression is not None:
            values[":topup"] = s(LedgerKind.TOPUP)

        request: QueryInputTypeDef = {
            "ExpressionAttributeValues": values,
            "KeyConditionExpression": OWN_PARTITION,
            "Limit": PAGE_SIZE if filter_expression else PAGE_SIZE + 1,
            "ScanIndexForward": order is LedgerOrder.ASC,
            "TableName": self.table.name,
        }
        if filter_expression is not None:
            request["FilterExpression"] = filter_expression
        if cursor is not None:
            request["ExclusiveStartKey"] = key(pk, cursor)

        response = await self.table.client.query(**request)

        if filter_expression is not None:
            last_evaluated = response.get("LastEvaluatedKey")
            next_cursor = last_evaluated["SK"]["S"] if last_evaluated is not None else None
            rows = response["Items"]
        else:
            rows = response["Items"][:PAGE_SIZE]
            has_more = len(response["Items"]) > PAGE_SIZE
            next_cursor = rows[-1]["SK"]["S"] if has_more else None

        return [LedgerEntry.model_validate(from_item(row)) for row in rows], next_cursor

    def _debit_item(self, account_id: str, entry: LedgerEntry) -> TransactWriteItemTypeDef:
        return {
            "Update": {
                "ConditionExpression": DEBIT_IF_COVERED,
                "ExpressionAttributeValues": {":amount": n(-entry.amount_micro)},
                "Key": account_key(account_id),
                "TableName": self.table.name,
                "UpdateExpression": DEBIT_BALANCE,
            }
        }

    def _ledger_put(self, account_id: str, entry: LedgerEntry) -> TransactWriteItemTypeDef:
        return {
            "Put": {
                "ConditionExpression": IF_ABSENT,
                "Item": {
                    **key(ledger_partition(account_id), ledger_sort_key(entry)),
                    **to_item(entry),
                },
                "TableName": self.table.name,
            }
        }

    async def _transact(self, *items: TransactWriteItemTypeDef) -> bool:
        write = condition_failed_as_false(self.table.client.transact_write_items)
        return await write(TransactItems=items)

    @condition_failed_as_false
    async def _put_if(self, item: dict[str, AttributeValueTypeDef], condition: str) -> None:
        await self.table.client.put_item(
            ConditionExpression=condition, Item=item, TableName=self.table.name
        )

    @condition_failed_as_false
    async def _update(
        self,
        item_key: dict[str, AttributeValueTypeDef],
        expression: str,
        values: Mapping[str, AttributeValueTypeDef],
        condition: str,
    ) -> None:
        if values:
            await self.table.client.update_item(
                ConditionExpression=condition,
                ExpressionAttributeValues=values,
                Key=item_key,
                TableName=self.table.name,
                UpdateExpression=expression,
            )
        else:
            await self.table.client.update_item(
                ConditionExpression=condition,
                Key=item_key,
                TableName=self.table.name,
                UpdateExpression=expression,
            )

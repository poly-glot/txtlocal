import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

import aioboto3

from txtlocal.shared import runtime, telemetry
from txtlocal.shared.table import PLATFORM, Table, n, s

if TYPE_CHECKING:
    from types_aiobotocore_dynamodb.type_defs import AttributeValueTypeDef

BOOST_RATE_MICRO = 42_700
DEDICATED_NUMBER_PRICE_MICRO = 2_650_000
RATES_MICRO: Mapping[tuple[str, str], int] = {
    ("CA", "MMS"): 150_000,
    ("CA", "SMS"): 8_000,
    ("GB", "MMS_AS_LINK"): 42_700,
    ("GB", "SMS"): 42_700,
    ("US", "MMS"): 150_000,
    ("US", "SMS"): 8_000,
}
GB_NUMBERS: Sequence[str] = (
    "+447984390718",
    "+447984390721",
    "+447984390734",
    "+447984390747",
    "+447984390752",
    "+447984390768",
    "+447984390775",
    "+447984390783",
    "+447984390796",
    "+447984390804",
    "+447984390812",
    "+447984390829",
    "+447984390837",
)


@dataclass(frozen=True, slots=True)
class Pack:
    amount_micro: int
    code: str
    name: str
    rate_micro: int
    savings_pct: int

    def bonus_micro(self) -> int:
        credit = round(self.amount_micro * BOOST_RATE_MICRO / self.rate_micro)
        return credit - self.amount_micro


PACKS: Sequence[Pack] = (
    Pack(10_000_000, "boost-10", "Top-up £10", BOOST_RATE_MICRO, 0),
    Pack(30_000_000, "boost-30", "Top-up £30", BOOST_RATE_MICRO, 0),
    Pack(50_000_000, "boost-50", "Top-up £50", BOOST_RATE_MICRO, 0),
    Pack(100_000_000, "boost-100", "Top-up £100", BOOST_RATE_MICRO, 0),
    Pack(300_000_000, "growth", "Growth pack", 38_700, 9),
    Pack(1_500_000_000, "scale", "Scale pack", 34_300, 19),
    Pack(4_000_000_000, "enterprise", "Enterprise pack", 31_300, 26),
)

type Item = dict[str, AttributeValueTypeDef]


def rate_items() -> list[Item]:
    return [
        {"PK": s(PLATFORM), "SK": s(f"RATE#{country}#{product}"), "priceMicro": n(price)}
        for (country, product), price in RATES_MICRO.items()
    ]


def pack_items() -> list[Item]:
    return [
        {
            "PK": s(PLATFORM),
            "SK": s(f"PACK#{pack.code}"),
            "amountMicro": n(pack.amount_micro),
            "bonusMicro": n(pack.bonus_micro()),
            "estimateCountry": s("GB"),
            "name": s(pack.name),
            "rateMicro": n(pack.rate_micro),
            "savingsPct": n(pack.savings_pct),
        }
        for pack in PACKS
    ]


def number_items() -> list[Item]:
    numbers: AttributeValueTypeDef = {
        "L": [
            {
                "M": {
                    "capabilities": {"L": [s("SMS")]},
                    "priceMicro": n(DEDICATED_NUMBER_PRICE_MICRO),
                    "value": s(value),
                }
            }
            for value in GB_NUMBERS
        ]
    }
    return [{"PK": s(PLATFORM), "SK": s("NUMBERS#GB"), "numbers": numbers}]


def platform_items() -> list[Item]:
    return [*rate_items(), *pack_items(), *number_items()]


async def seed_platform(table: Table) -> int:
    items = platform_items()
    for item in items:
        await table.client.put_item(TableName=table.name, Item=item)
    return len(items)


async def main() -> int:
    session = aioboto3.Session()
    endpoint = os.environ.get("AWS_ENDPOINT_URL_DYNAMODB")
    region = os.environ.get("AWS_REGION")
    async with session.client("dynamodb", endpoint_url=endpoint, region_name=region) as client:
        table = Table(client=client, name=os.environ["TABLE_NAME"])
        count = await seed_platform(table)
    telemetry.log("seeded", items=count, table=table.name)
    sys.stdout.write(f"seeded {count} platform rows into {table.name}\n")
    return 0


if __name__ == "__main__":
    telemetry.configure()
    raise SystemExit(runtime.run(main()))

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Protocol, assert_never

from txtlocal.shared.errors import Upstream
from txtlocal.shared.money import Micro
from txtlocal.slices.senders.model import CatalogueNumber, Channel, NumberCataloguePage, UseFor

if TYPE_CHECKING:
    from types_aiobotocore_pinpoint_sms_voice_v2 import PinpointSMSVoiceV2Client

CATALOGUE_BASE = 447_984_390_700
CATALOGUE_COUNTRY = "GB"
CATALOGUE_SIZE = 40
DEDICATED_MONTHLY_PRICE_MICRO = Micro(2_650_000)
NUMBER_SEARCH_UNAVAILABLE = "Number search is not available yet"
PAGE_SIZE = 13


class NumberCatalogue(Protocol):
    async def search(
        self, country: str, use_for: UseFor | None, contains: str, page: int
    ) -> NumberCataloguePage: ...

    async def get(self, value: str) -> CatalogueNumber | None: ...


def matches_use_for(number: CatalogueNumber, use_for: UseFor | None) -> bool:
    if use_for is None:
        return True
    match use_for:
        case UseFor.MMS:
            return Channel.MMS in number.capabilities
        case UseFor.SMS:
            return Channel.SMS in number.capabilities
        case UseFor.SMS_MMS:
            return Channel.MMS in number.capabilities and Channel.SMS in number.capabilities
        case _ as unreachable:
            assert_never(unreachable)


def seeded_catalogue() -> tuple[CatalogueNumber, ...]:
    return tuple(
        CatalogueNumber(
            capabilities=(Channel.MMS, Channel.SMS) if i % 2 else (Channel.SMS,),
            country=CATALOGUE_COUNTRY,
            monthly_price_micro=DEDICATED_MONTHLY_PRICE_MICRO,
            value=f"+{CATALOGUE_BASE + i}",
        )
        for i in range(CATALOGUE_SIZE)
    )


@dataclass(frozen=True, slots=True)
class FakeNumberCatalogue:
    numbers: ClassVar[tuple[CatalogueNumber, ...]] = seeded_catalogue()

    async def search(
        self, country: str, use_for: UseFor | None, contains: str, page: int
    ) -> NumberCataloguePage:
        matching = [
            number
            for number in self.numbers
            if number.country == country
            and matches_use_for(number, use_for)
            and contains in number.value
        ]
        total_pages = max(1, math.ceil(len(matching) / PAGE_SIZE))
        start = (page - 1) * PAGE_SIZE
        return NumberCataloguePage(
            numbers=matching[start : start + PAGE_SIZE], page=page, total_pages=total_pages
        )

    async def get(self, value: str) -> CatalogueNumber | None:
        return next((number for number in self.numbers if number.value == value), None)


@dataclass(frozen=True, slots=True)
class AwsNumberCatalogue:
    client: PinpointSMSVoiceV2Client

    async def search(
        self, _country: str, _use_for: UseFor | None, _contains: str, _page: int
    ) -> NumberCataloguePage:
        raise Upstream(NUMBER_SEARCH_UNAVAILABLE)

    async def get(self, _value: str) -> CatalogueNumber | None:
        raise Upstream(NUMBER_SEARCH_UNAVAILABLE)

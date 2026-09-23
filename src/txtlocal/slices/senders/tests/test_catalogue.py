import pytest

from txtlocal.shared.money import Micro
from txtlocal.slices.senders.catalogue import (
    CATALOGUE_SIZE,
    PAGE_SIZE,
    FakeNumberCatalogue,
    matches_use_for,
)
from txtlocal.slices.senders.model import CatalogueNumber, Channel, UseFor

PRICE = Micro(2_650_000)
SMS_ONLY = CatalogueNumber(
    capabilities=(Channel.SMS,), country="GB", monthly_price_micro=PRICE, value="+1"
)
SMS_AND_MMS = CatalogueNumber(
    capabilities=(Channel.MMS, Channel.SMS), country="GB", monthly_price_micro=PRICE, value="+2"
)


@pytest.mark.parametrize(
    ("number", "use_for", "expected"),
    [
        (SMS_ONLY, None, True),
        (SMS_ONLY, UseFor.SMS, True),
        (SMS_ONLY, UseFor.MMS, False),
        (SMS_ONLY, UseFor.SMS_MMS, False),
        (SMS_AND_MMS, UseFor.SMS, True),
        (SMS_AND_MMS, UseFor.MMS, True),
        (SMS_AND_MMS, UseFor.SMS_MMS, True),
    ],
    ids=[
        "no-filter-matches-anything",
        "sms-only-matches-sms-filter",
        "sms-only-refused-by-mms-filter",
        "sms-only-refused-by-both-filter",
        "sms-and-mms-matches-sms-filter",
        "sms-and-mms-matches-mms-filter",
        "sms-and-mms-matches-both-filter",
    ],
)
def test_matches_use_for(number: CatalogueNumber, use_for: UseFor | None, expected: bool) -> None:
    assert matches_use_for(number, use_for) is expected


async def test_seeded_catalogue_has_forty_numbers_alternating_use_for() -> None:
    catalogue = FakeNumberCatalogue()

    first_page = await catalogue.search("GB", None, "", 1)
    fourth_page = await catalogue.search("GB", None, "", 4)

    assert first_page.total_pages == 4
    assert len(first_page.numbers) == PAGE_SIZE
    assert len(fourth_page.numbers) == CATALOGUE_SIZE - 3 * PAGE_SIZE
    assert [number.capabilities for number in first_page.numbers[:2]] == [
        (Channel.SMS,),
        (Channel.MMS, Channel.SMS),
    ]


async def test_search_filters_by_country() -> None:
    catalogue = FakeNumberCatalogue()

    page = await catalogue.search("US", None, "", 1)

    assert page.numbers == []
    assert page.total_pages == 1


async def test_get_finds_a_seeded_number_by_value() -> None:
    catalogue = FakeNumberCatalogue()
    [first, *_rest] = (await catalogue.search("GB", None, "", 1)).numbers

    found = await catalogue.get(first.value)

    assert found == first


async def test_get_is_none_for_an_unseeded_number() -> None:
    catalogue = FakeNumberCatalogue()

    assert await catalogue.get("+447000000000") is None

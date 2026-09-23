import pytest

from txtlocal.shared.errors import BadRequest
from txtlocal.shared.phone import E164, INVALID_NUMBER_MESSAGE, country_of, normalise


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("07400 123456", "+447400123456"),
        ("+447400123456", "+447400123456"),
        ("+1 202 555 0143", "+12025550143"),
    ],
    ids=["gb-national", "already-e164", "us-with-spaces"],
)
def test_normalise(raw: str, expected: str) -> None:
    assert normalise(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["hello", "", "07700 900123", "202 555 0143"],
    ids=["letters", "empty", "gb-national-reserved-range", "us-number-without-its-code"],
)
def test_normalise_asks_for_the_international_format(raw: str) -> None:
    with pytest.raises(BadRequest) as caught:
        normalise(raw)
    assert str(caught.value) == INVALID_NUMBER_MESSAGE


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ("+447700900123", "That is not a valid +44 number; check the digits"),
        ("00447700900123", "That is not a valid +44 number; check the digits"),
        ("+44 12", "That is not a valid +44 number; check the digits"),
        ("+1 202 555 01", "That is not a valid +1 number; check the digits"),
    ],
    ids=["gb-reserved-range", "gb-with-idd-prefix", "gb-too-short", "us-too-short"],
)
def test_normalise_says_the_digits_are_wrong_when_the_country_code_is_given(
    raw: str, message: str
) -> None:
    with pytest.raises(BadRequest) as caught:
        normalise(raw)
    assert str(caught.value) == message


def test_country_of() -> None:
    assert country_of(E164("+447400123456")) == "GB"

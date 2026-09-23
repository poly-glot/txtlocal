from typing import NewType

import phonenumbers
from phonenumbers import CountryCodeSource, NumberParseException, PhoneNumber, PhoneNumberFormat

from txtlocal.shared.errors import BadRequest

E164 = NewType("E164", str)

INVALID_DIGITS_MESSAGE = "That is not a valid +{code} number; check the digits"
INVALID_NUMBER_MESSAGE = "Enter the number in international format, for example +447400123123"
UNKNOWN_COUNTRY = "ZZ"


def normalise(raw: str, default_region: str = "GB") -> E164:
    try:
        parsed = phonenumbers.parse(raw, default_region, keep_raw_input=True)
    except NumberParseException as error:
        raise BadRequest(INVALID_NUMBER_MESSAGE) from error

    if not phonenumbers.is_valid_number(parsed):
        raise BadRequest(invalid_number_message(parsed))

    return E164(phonenumbers.format_number(parsed, PhoneNumberFormat.E164))


def invalid_number_message(parsed: PhoneNumber) -> str:
    if parsed.country_code_source == CountryCodeSource.FROM_DEFAULT_COUNTRY:
        return INVALID_NUMBER_MESSAGE
    return INVALID_DIGITS_MESSAGE.format(code=parsed.country_code)


def country_of(number: E164) -> str:
    return phonenumbers.region_code_for_number(phonenumbers.parse(number)) or UNKNOWN_COUNTRY

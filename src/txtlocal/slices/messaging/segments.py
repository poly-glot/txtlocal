import math
from enum import StrEnum
from typing import assert_never

GSM7_BASIC = frozenset(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXTENSION = frozenset("\f^{}\\[~]|€")

GSM7_SINGLE = 160
GSM7_PART = 153
UCS2_SINGLE = 70
UCS2_PART = 67
MAX_PARTS_CEILING = 8
MAX_CHARS = MAX_PARTS_CEILING * GSM7_PART


class Encoding(StrEnum):
    GSM7 = "GSM7"
    UCS2 = "UCS2"


def first_non_gsm(body: str) -> str | None:
    return next((char for char in body if not is_gsm(char)), None)


def is_gsm(char: str) -> bool:
    return char in GSM7_BASIC or char in GSM7_EXTENSION


def encoding_of(body: str) -> Encoding:
    if first_non_gsm(body) is None:
        return Encoding.GSM7
    return Encoding.UCS2


def units_of(body: str, encoding: Encoding) -> int:
    match encoding:
        case Encoding.GSM7:
            return sum(2 if char in GSM7_EXTENSION else 1 for char in body)
        case Encoding.UCS2:
            return len(body.encode("utf-16-be")) // 2
        case _:
            assert_never(encoding)


def limits_of(encoding: Encoding) -> tuple[int, int]:
    match encoding:
        case Encoding.GSM7:
            return GSM7_SINGLE, GSM7_PART
        case Encoding.UCS2:
            return UCS2_SINGLE, UCS2_PART
        case _:
            assert_never(encoding)


def segments_of(body: str, encoding: Encoding) -> int:
    units = units_of(body, encoding)
    if units == 0:
        return 0

    single, part = limits_of(encoding)
    if units <= single:
        return 1
    return math.ceil(units / part)

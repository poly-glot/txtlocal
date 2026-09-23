from decimal import ROUND_HALF_UP, Decimal
from typing import NewType

Micro = NewType("Micro", int)

MICRO_PER_PENCE = 10_000
MICRO_PER_POUND = 1_000_000
MIN_PLACES = 2
PRICE_PLACES = 4


def micro_to_pence(micro: Micro) -> int:
    return micro // MICRO_PER_PENCE


def format_gbp(micro: Micro, places: int = 2) -> str:
    pounds = (Decimal(abs(micro)) / MICRO_PER_POUND).quantize(
        Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP
    )
    sign = "-" if micro < 0 else ""
    return f"{sign}£{pounds}"


def format_price(micro: Micro) -> str:
    exact = format_gbp(micro, PRICE_PLACES)
    trimmed = exact.rstrip("0")
    decimals = len(trimmed.split(".")[1]) if "." in trimmed else 0
    return exact[: len(exact) - (PRICE_PLACES - max(decimals, MIN_PLACES))]


def format_decimal(micro: Micro) -> str:
    return format_price(micro).removeprefix("£")

import pytest

from txtlocal.shared.money import Micro, format_gbp, micro_to_pence


@pytest.mark.parametrize(
    ("micro", "places", "expected"),
    [
        (Micro(42_700), 4, "£0.0427"),
        (Micro(42_700), 2, "£0.04"),
        (Micro(45_000), 2, "£0.05"),
        (Micro(44_999), 2, "£0.04"),
        (Micro(2_000_000), 2, "£2.00"),
        (Micro(-1_500_000), 2, "-£1.50"),
        (Micro(0), 2, "£0.00"),
    ],
    ids=[
        "four-places-keeps-sub-penny",
        "two-places-rounds-down",
        "half-rounds-up",
        "just-under-half-rounds-down",
        "whole-pounds",
        "negative-keeps-sign-before-symbol",
        "zero",
    ],
)
def test_format_gbp(micro: Micro, places: int, expected: str) -> None:
    assert format_gbp(micro, places) == expected


@pytest.mark.parametrize(
    ("micro", "expected"),
    [(Micro(49_999), 4), (Micro(50_000), 5), (Micro(0), 0), (Micro(-1), -1)],
    ids=["floors-just-under", "exact", "zero", "negative-floors-away-from-zero"],
)
def test_micro_to_pence_floors(micro: Micro, expected: int) -> None:
    assert micro_to_pence(micro) == expected

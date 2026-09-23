from datetime import datetime, timedelta

import pytest

from txtlocal.shared.money import Micro
from txtlocal.slices.billing.model import BillingAccount
from txtlocal.slices.billing.service import (
    BOOSTS,
    PACKS,
    boost_view,
    can_send,
    crosses_below,
    insufficient_balance,
    is_within_trial,
    pack_view,
    trial_days_left,
)
from txtlocal.slices.billing.tests.fakes import NOW, ZERO

BASE_RATE_MICRO = Micro(42_700)

ONE_MICROSECOND = timedelta(microseconds=1)
ONE_SECOND = timedelta(seconds=1)
ONE_DAY = timedelta(days=1)


@pytest.mark.parametrize(
    ("trial_ends_at", "expected"),
    [(NOW + ONE_MICROSECOND, True), (NOW, False), (None, False)],
    ids=["one-microsecond-left", "at-the-end", "no-trial"],
)
def test_is_within_trial(trial_ends_at: datetime | None, expected: bool) -> None:
    assert is_within_trial(trial_ends_at, NOW) is expected


@pytest.mark.parametrize(
    ("has_topped_up", "trial_ends_at", "expected"),
    [
        (False, NOW + ONE_DAY, True),
        (False, NOW, False),
        (True, NOW - ONE_DAY, True),
        (True, None, True),
    ],
    ids=["in-trial", "trial-over-without-top-up", "topped-up-after-trial", "topped-up-no-trial"],
)
def test_can_send(has_topped_up: bool, trial_ends_at: datetime | None, expected: bool) -> None:
    account = BillingAccount(
        balance_micro=ZERO, has_topped_up=has_topped_up, trial_ends_at=trial_ends_at
    )
    assert can_send(account, NOW) is expected


@pytest.mark.parametrize(
    ("trial_ends_at", "expected"),
    [
        (NOW + 14 * ONE_DAY, 14),
        (NOW + 14 * ONE_DAY - ONE_SECOND, 14),
        (NOW + ONE_DAY, 1),
        (NOW + ONE_SECOND, 1),
        (NOW, 0),
        (NOW - ONE_SECOND, 0),
        (None, 0),
    ],
    ids=[
        "fresh-trial",
        "a-second-into-the-trial-still-fourteen",
        "exactly-one-day",
        "last-second-counts-as-a-day",
        "at-the-end",
        "expired",
        "no-trial",
    ],
)
def test_trial_days_left(trial_ends_at: datetime | None, expected: int) -> None:
    assert trial_days_left(trial_ends_at, NOW) == expected


@pytest.mark.parametrize(
    ("balance_micro", "cost_micro", "expected"),
    [
        (Micro(1_964_999), Micro(2_000_000), "Your balance is £1.965; this send costs £2.00"),
        (Micro(1_965_000), Micro(42_700), "Your balance is £1.965; this send costs £0.0427"),
        (Micro(0), Micro(1), "Your balance is £0.00; this send costs £0.00"),
    ],
    ids=["rounds-down", "half-rounds-up", "sub-penny-shows-as-zero"],
)
def test_insufficient_balance_formats_two_places(
    balance_micro: Micro, cost_micro: Micro, expected: str
) -> None:
    assert insufficient_balance(balance_micro, cost_micro) == expected


@pytest.mark.parametrize(
    ("code", "amount_micro", "expected_estimate"),
    [
        ("BOOST_10", 10_000_000, 234),
        ("BOOST_30", 30_000_000, 702),
        ("BOOST_50", 50_000_000, 1_170),
        ("BOOST_100", 100_000_000, 2_341),
    ],
    ids=["boost-10", "boost-30", "boost-50", "boost-100"],
)
def test_boost_estimate_matches_the_screen(
    code: str, amount_micro: int, expected_estimate: int
) -> None:
    spec = next(boost for boost in BOOSTS if boost.code == code)
    assert spec.amount_micro == amount_micro

    view = boost_view(spec, BASE_RATE_MICRO)

    assert view.estimate == expected_estimate


@pytest.mark.parametrize(
    ("code", "expected_estimate", "expected_savings_pct"),
    [("GROWTH", 7_751, 9), ("SCALE", 43_731, 19), ("ENTERPRISE", 127_795, 26)],
    ids=["growth", "scale", "enterprise"],
)
def test_pack_estimate_and_savings_match_the_screen(
    code: str, expected_estimate: int, expected_savings_pct: int
) -> None:
    spec = next(pack for pack in PACKS if pack.code == code)

    view = pack_view(spec, BASE_RATE_MICRO)

    assert (view.estimate, view.savings_pct) == (expected_estimate, expected_savings_pct)


@pytest.mark.parametrize(
    ("before_micro", "after_micro", "expected"),
    [
        (Micro(6_000_000), Micro(4_000_000), True),
        (Micro(5_000_000), Micro(4_999_999), True),
        (Micro(4_999_999), Micro(1), False),
        (Micro(10_000_000), Micro(9_000_000), False),
        (Micro(5_000_000), Micro(5_000_000), False),
    ],
    ids=[
        "crosses-from-well-above",
        "crosses-from-exactly-at-threshold",
        "already-below-is-not-a-crossing",
        "stays-above-no-crossing",
        "lands-exactly-on-the-threshold-is-not-below",
    ],
)
def test_crosses_below_the_threshold(
    before_micro: Micro, after_micro: Micro, expected: bool
) -> None:
    assert crosses_below(before_micro, after_micro, Micro(5_000_000)) is expected


def test_growth_pack_credits_the_given_micro_pound_amount() -> None:
    spec = next(pack for pack in PACKS if pack.code == "GROWTH")

    view = pack_view(spec, BASE_RATE_MICRO)

    assert view.credited_micro == 331_007_751

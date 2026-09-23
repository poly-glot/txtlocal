from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

from txtlocal.shared.money import Micro
from txtlocal.shared.phone import E164
from txtlocal.slices.messaging.model import RefusalReason
from txtlocal.slices.messaging.policy import AccountState, Allowed, Refused
from txtlocal.slices.messaging.tests.support import DESTINATION, MAX_PRICE_USD, NOW, policy

FRENCH_NUMBER = E164("+33612345678")
QUOTE = Micro(42_700)
TOMORROW = NOW + timedelta(days=1)


@dataclass(frozen=True, slots=True)
class SenderStub:
    country: str = "GB"
    display: str = "Shared Number"
    kind: str = "SHARED"
    status: str = "READY"


def account(
    *,
    balance_micro: int = 1_000_000,
    has_topped_up: bool = False,
    opted_out: frozenset[E164] = frozenset(),
    sends_today: int = 0,
    trial_ends_at: datetime = TOMORROW,
    verified_numbers: frozenset[E164] = frozenset(),
) -> AccountState:
    return AccountState(
        balance_micro=Micro(balance_micro),
        has_topped_up=has_topped_up,
        opted_out=opted_out,
        sends_today=sends_today,
        trial_ends_at=trial_ends_at,
        verified_numbers=verified_numbers,
    )


OWN_NUMBER = SenderStub(
    display="+447411972333 (Own Number)", kind="OWN", status="PENDING_VERIFICATION"
)


@pytest.mark.parametrize(
    ("state", "sender", "destination", "sandbox", "expected"),
    [
        (
            account(),
            SenderStub(),
            FRENCH_NUMBER,
            False,
            Refused(
                message="Sending to FR is not enabled for this account",
                reason=RefusalReason.COUNTRY_NOT_ENABLED,
            ),
        ),
        (
            account(opted_out=frozenset({DESTINATION})),
            SenderStub(),
            DESTINATION,
            False,
            Refused(message="This contact has opted out", reason=RefusalReason.OPTED_OUT),
        ),
        (
            account(trial_ends_at=NOW),
            SenderStub(),
            DESTINATION,
            False,
            Refused(
                message="Your free trial has ended. Top up to keep sending",
                reason=RefusalReason.TRIAL_ENDED,
            ),
        ),
        (
            account(balance_micro=1_000_000),
            SenderStub(),
            DESTINATION,
            False,
            Refused(
                message="Your balance is £1.00; this send costs £1.50",
                reason=RefusalReason.INSUFFICIENT_BALANCE,
            ),
        ),
        (
            account(sends_today=500),
            SenderStub(),
            DESTINATION,
            False,
            Refused(message="Daily sending limit reached", reason=RefusalReason.DAILY_CAP),
        ),
        (
            account(),
            OWN_NUMBER,
            DESTINATION,
            False,
            Refused(
                message="+447411972333 (Own Number) is not ready to send to GB",
                reason=RefusalReason.SENDER_NOT_READY,
            ),
        ),
        (
            account(),
            SenderStub(),
            DESTINATION,
            True,
            Refused(
                message="While your account is in trial you can send to your verified numbers only",
                reason=RefusalReason.NOT_VERIFIED,
            ),
        ),
    ],
    ids=[
        "country-not-enabled",
        "opted-out",
        "trial-ended",
        "insufficient-balance",
        "daily-cap",
        "sender-not-ready",
        "not-verified-in-sandbox",
    ],
)
def test_allow_refuses_each_row_of_the_policy_table(
    state: AccountState,
    sender: SenderStub,
    destination: E164,
    sandbox: bool,
    expected: Refused,
) -> None:
    quote = Micro(1_500_000) if expected.reason is RefusalReason.INSUFFICIENT_BALANCE else QUOTE

    assert policy(sandbox=sandbox).allow(state, sender, destination, quote, NOW) == expected


def test_allow_carries_the_max_price() -> None:
    assert policy().allow(account(), SenderStub(), DESTINATION, QUOTE, NOW) == Allowed(
        max_price_usd=MAX_PRICE_USD
    )


def test_the_first_refusal_in_table_order_wins() -> None:
    state = account(opted_out=frozenset({FRENCH_NUMBER}))

    result = policy().allow(state, SenderStub(), FRENCH_NUMBER, QUOTE, NOW)

    assert isinstance(result, Refused)
    assert result.reason is RefusalReason.COUNTRY_NOT_ENABLED


@pytest.mark.parametrize(
    ("balance_micro", "outcome"),
    [(42_700, Allowed(max_price_usd=MAX_PRICE_USD)), (42_699, RefusalReason.INSUFFICIENT_BALANCE)],
    ids=["balance-equal-to-the-quote-sends", "one-micro-short-is-refused"],
)
def test_balance_ceiling(balance_micro: int, outcome: Allowed | RefusalReason) -> None:
    result = policy().allow(
        account(balance_micro=balance_micro), SenderStub(), DESTINATION, QUOTE, NOW
    )

    assert result == outcome or (isinstance(result, Refused) and result.reason is outcome)


@pytest.mark.parametrize(
    ("sends_today", "allowed"),
    [(499, True), (500, False)],
    ids=["499-sends-leave-room-for-the-500th", "500-sends-hit-the-cap"],
)
def test_daily_cap_ceiling(sends_today: int, allowed: bool) -> None:
    result = policy().allow(account(sends_today=sends_today), SenderStub(), DESTINATION, QUOTE, NOW)

    assert isinstance(result, Allowed) is allowed


@pytest.mark.parametrize(
    ("trial_ends_at", "has_topped_up", "allowed"),
    [
        (NOW + timedelta(seconds=1), False, True),
        (NOW, False, False),
        (NOW, True, True),
    ],
    ids=["one-second-of-trial-left", "trial-ends-now", "topped-up-outlives-the-trial"],
)
def test_trial_ceiling(trial_ends_at: datetime, has_topped_up: bool, allowed: bool) -> None:
    state = account(has_topped_up=has_topped_up, trial_ends_at=trial_ends_at)

    result = policy().allow(state, SenderStub(), DESTINATION, QUOTE, NOW)

    assert isinstance(result, Allowed) is allowed


@pytest.mark.parametrize(
    ("sender", "allowed"),
    [
        (SenderStub(country="US", kind="SHARED"), True),
        (SenderStub(country="US", kind="DEDICATED", display="+12065550100"), False),
        (SenderStub(country="GB", kind="DEDICATED", display="+447984390718"), True),
        (SenderStub(kind="ALPHA", status="UNDER_REVIEW", display="TXTLOCAL"), False),
    ],
    ids=[
        "shared-serves-every-country",
        "dedicated-for-another-country",
        "dedicated-for-the-destination-country",
        "alpha-tag-under-review",
    ],
)
def test_sender_readiness(sender: SenderStub, allowed: bool) -> None:
    result = policy().allow(account(), sender, DESTINATION, QUOTE, NOW)

    assert isinstance(result, Allowed) is allowed


def test_sandbox_allows_a_verified_number() -> None:
    state = account(verified_numbers=frozenset({DESTINATION}))

    result = policy(sandbox=True).allow(state, SenderStub(), DESTINATION, QUOTE, NOW)

    assert result == Allowed(max_price_usd=MAX_PRICE_USD)

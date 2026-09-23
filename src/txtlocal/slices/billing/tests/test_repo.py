from datetime import timedelta
from uuid import UUID

import pytest

from txtlocal.shared.errors import Internal
from txtlocal.shared.money import Micro
from txtlocal.slices.billing.model import BillingAccount, LedgerEntry, LedgerKind
from txtlocal.slices.billing.repo import (
    REFUND_WITHOUT_REF,
    TRIAL_SK,
    from_item,
    ledger_sort_key,
    minted_at,
    to_item,
)
from txtlocal.slices.billing.tests.fakes import NOW, ZERO, uuid7_at

ENTRY_ID = "0192f1a2-0000-7000-8000-00000000e17f"
CAMPAIGN_MINTED_AT = NOW - timedelta(seconds=1)
CAMPAIGN_ID = uuid7_at(CAMPAIGN_MINTED_AT)


def entry(kind: LedgerKind, ref: str | None = None) -> LedgerEntry:
    return LedgerEntry(
        amount_micro=Micro(-42_700),
        balance_after_micro=Micro(1_957_300),
        created_at=NOW,
        entry_id=ENTRY_ID,
        kind=kind,
        ref=ref,
    )


def test_uuid7_at_builds_a_version_seven_id() -> None:
    assert UUID(CAMPAIGN_ID).version == 7


def test_minted_at_reads_the_millisecond_a_uuid7_was_minted() -> None:
    assert minted_at(CAMPAIGN_ID) == CAMPAIGN_MINTED_AT


@pytest.mark.parametrize(
    ("kind", "ref", "expected"),
    [
        (LedgerKind.TRIAL, None, TRIAL_SK),
        (LedgerKind.SEND, CAMPAIGN_ID, f"2026-09-19T12:00:00.000Z#{ENTRY_ID}"),
        (LedgerKind.REFUND, CAMPAIGN_ID, f"2026-09-19T11:59:59.000Z#{CAMPAIGN_ID}"),
        (LedgerKind.TOPUP, "pi_123", f"2026-09-19T12:00:00.000Z#{ENTRY_ID}"),
    ],
    ids=[
        "trial-has-a-fixed-key",
        "send-sorts-at-its-own-time",
        "refund-sorts-at-the-campaign-mint-time-under-the-ref",
        "topup-sorts-at-its-own-time",
    ],
)
def test_ledger_sort_key(kind: LedgerKind, ref: str | None, expected: str) -> None:
    assert ledger_sort_key(entry(kind, ref)) == expected


def test_refund_without_a_ref_is_internal() -> None:
    with pytest.raises(Internal) as caught:
        ledger_sort_key(entry(LedgerKind.REFUND))
    assert str(caught.value) == REFUND_WITHOUT_REF


def test_item_round_trips_a_ledger_entry() -> None:
    send = entry(LedgerKind.SEND, CAMPAIGN_ID)
    assert LedgerEntry.model_validate(from_item(to_item(send))) == send


def test_item_omits_absent_optionals() -> None:
    assert "ref" not in to_item(entry(LedgerKind.TRIAL))


def test_item_writes_booleans_and_numbers_natively() -> None:
    item = to_item(BillingAccount(balance_micro=ZERO, has_topped_up=False))
    assert (item["hasToppedUp"], item["balanceMicro"]) == ({"BOOL": False}, {"N": "0"})

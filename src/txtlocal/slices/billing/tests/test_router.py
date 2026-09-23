from datetime import timedelta

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from txtlocal.shared.errors import Forbidden
from txtlocal.shared.money import Micro
from txtlocal.slices.billing.gateway import PaymentEvent
from txtlocal.slices.billing.model import TopUp, TopUpKind, TopUpStatus
from txtlocal.slices.billing.router import OWNER_ONLY, Authenticated, build_router
from txtlocal.slices.billing.tests.fakes import (
    ACCOUNT_ID,
    NOW,
    InMemoryBillingRepo,
    account_row,
    billing,
    uuid7_at,
)
from txtlocal.slices.identity.model import Principal, Role

OWNER = Principal(account_id=ACCOUNT_ID, role=Role.OWNER, user_id="u-owner", username="owner")
SUB = Principal(account_id=ACCOUNT_ID, role=Role.SUB, user_id="u-sub", username="sub")
TRIAL_ENDS_AT = NOW + timedelta(days=13)


def signed_in_as(principal: Principal) -> Authenticated:
    async def authenticated(_: Request) -> Principal:
        return principal

    return authenticated


def client_for(repo: InMemoryBillingRepo, principal: Principal) -> TestClient:
    app = FastAPI()
    app.include_router(build_router(billing(repo), signed_in_as(principal)))
    return TestClient(app)


def trial_repo() -> InMemoryBillingRepo:
    repo = InMemoryBillingRepo()
    account_row(repo, balance_micro=Micro(1_957_300), trial_ends_at=TRIAL_ENDS_AT)
    return repo


def test_summary_answers_balance_recharge_thresholds_and_trial() -> None:
    response = client_for(trial_repo(), OWNER).get("/api/app/billing/summary")

    assert response.status_code == 200
    assert response.json() == {
        "autoRecharge": False,
        "balanceMicro": 1_957_300,
        "canSend": True,
        "hasToppedUp": False,
        "lowBalanceThresholdMicro": 5_000_000,
        "rechargeAmountMicro": 10_000_000,
        "trialDaysLeft": 13,
        "trialEndsAt": "2026-10-02T12:00:00Z",
    }


async def test_transactions_lists_paid_top_ups_only() -> None:
    repo = trial_repo()
    campaign_id = uuid7_at(NOW)
    service = billing(repo)
    await service.reserve(ACCOUNT_ID, Micro(42_700), campaign_id, NOW)

    top_up_id = uuid7_at(NOW)
    await repo.put_topup(
        TopUp(
            account_id=ACCOUNT_ID,
            amount_micro=Micro(10_000_000),
            code="BOOST_10",
            created_at=NOW,
            credited_micro=Micro(10_000_000),
            kind=TopUpKind.BOOST,
            status=TopUpStatus.PENDING,
            top_up_id=top_up_id,
        )
    )
    await service.credit_top_up(
        PaymentEvent(
            event_id="evt_1",
            event_type="checkout.session.completed",
            account_id=ACCOUNT_ID,
            top_up_id=top_up_id,
        ),
        NOW,
    )

    response = client_for(repo, OWNER).get("/api/app/billing/transactions")

    assert response.status_code == 200
    body = response.json()
    assert body["nextCursor"] is None
    assert [(row["kind"], row["amountMicro"]) for row in body["items"]] == [("TOPUP", 10_000_000)]


def test_transactions_treat_an_empty_cursor_as_the_first_page() -> None:
    response = client_for(trial_repo(), OWNER).get("/api/app/billing/transactions?cursor=")

    assert response.json() == {"items": [], "nextCursor": None}


@pytest.mark.parametrize(
    "path",
    [
        "/api/app/billing/summary",
        "/api/app/billing/transactions",
        "/api/app/billing/packages",
        "/api/app/billing/general",
        "/api/app/billing/cards",
        "/api/app/billing/upcoming-charges",
    ],
    ids=["summary", "transactions", "packages", "general", "cards", "upcoming-charges"],
)
def test_sub_accounts_are_forbidden(path: str) -> None:
    client = client_for(trial_repo(), SUB)

    with pytest.raises(Forbidden) as caught:
        client.get(path)
    assert str(caught.value) == OWNER_ONLY


def test_transactions_refuse_an_unknown_order() -> None:
    response = client_for(trial_repo(), OWNER).get("/api/app/billing/transactions?order=newest")

    assert response.status_code == 422

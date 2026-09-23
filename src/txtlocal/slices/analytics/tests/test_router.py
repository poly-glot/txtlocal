from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from txtlocal.shared.money import Micro
from txtlocal.slices.analytics.model import TrackedLink, UsageLine
from txtlocal.slices.analytics.router import build_public_router, build_router
from txtlocal.slices.analytics.service import AnalyticsService
from txtlocal.slices.analytics.tests.fakes import (
    ACCOUNT_ID,
    NOW,
    FakeAnalyticsRepo,
    FakeClickQueries,
    FakeUsageQueries,
)
from txtlocal.slices.identity.model import Principal, Role
from txtlocal.slices.messaging.model import Product

PRINCIPAL = Principal(
    account_id=ACCOUNT_ID, role=Role.OWNER, user_id="usr-1", username="user@example.com"
)


async def authenticated(_request: Request) -> Principal:
    return PRINCIPAL


def service_over(repo: FakeAnalyticsRepo) -> AnalyticsService:
    return AnalyticsService(
        click_queries=FakeClickQueries(results=[]),
        clock=lambda: NOW,
        public_base_url="https://app.txtlocal.example",
        repo=repo,
        usage_queries=FakeUsageQueries(results=[]),
    )


def client_of(service: AnalyticsService) -> TestClient:
    app = FastAPI()
    app.include_router(build_router(service, authenticated))
    app.include_router(build_public_router(service))
    return TestClient(app)


def a_link(code: str) -> TrackedLink:
    return TrackedLink(
        account_id=ACCOUNT_ID,
        campaign_id="",
        clicks_total=0,
        code=code,
        created_at=NOW,
        last_rollup=None,
        url="https://example.com/target",
    )


def test_redirect_answers_404_for_a_malformed_code() -> None:
    client = client_of(service_over(FakeAnalyticsRepo()))

    response = client.get("/l/too-short", follow_redirects=False)

    assert response.status_code == 404


def test_redirect_answers_404_for_an_unknown_code() -> None:
    client = client_of(service_over(FakeAnalyticsRepo()))

    response = client.get("/l/ab3de5fgh7", follow_redirects=False)

    assert response.status_code == 404


def test_redirect_404_is_never_cached() -> None:
    client = client_of(service_over(FakeAnalyticsRepo()))

    response = client.get("/l/ab3de5fgh7", follow_redirects=False)

    assert response.headers["cache-control"] == "no-store"


def test_redirect_answers_302_with_cache_control_for_a_known_code() -> None:
    repo = FakeAnalyticsRepo(links={"ab3de5fgh7": a_link("ab3de5fgh7")})
    client = client_of(service_over(repo))

    response = client.get("/l/ab3de5fgh7", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/target"
    assert response.headers["cache-control"] == "public, max-age=300"


def test_usage_answers_200_with_the_months_rows() -> None:
    repo = FakeAnalyticsRepo(
        usage_rows=[
            UsageLine(
                account_id=ACCOUNT_ID,
                cost_micro=Micro(42700),
                country="GB",
                day="2026-09-18",
                product=Product.SMS,
                quantity=1,
                sender_id="snd-1",
                user_id="usr-1",
            )
        ]
    )
    client = client_of(service_over(repo))

    response = client.get("/api/app/analytics/usage", params={"month": "2026-09"})

    assert response.status_code == 200
    assert response.json()["rows"] == [
        {"costMicro": 42700, "month": "2026-09", "product": "SMS", "quantity": 1, "userId": "usr-1"}
    ]


def test_usage_rejects_a_malformed_month() -> None:
    client = client_of(service_over(FakeAnalyticsRepo()))

    response = client.get("/api/app/analytics/usage", params={"month": "September"})

    assert response.status_code == 422


def test_reporting_answers_200_with_paging_fields() -> None:
    client = client_of(service_over(FakeAnalyticsRepo()))

    response = client.get(
        "/api/app/analytics/reporting", params={"since": "2026-07-01", "until": "2026-09-18"}
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["page"], body["pageSize"], body["totalResults"]) == (1, 10, 0)


def test_reporting_export_streams_csv() -> None:
    client = client_of(service_over(FakeAnalyticsRepo()))

    response = client.get(
        "/api/app/analytics/reporting/export", params={"since": "2026-07-01", "until": "2026-09-18"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="usage-reporting.csv"'
    assert (
        response.text.splitlines()[0] == "date,product,userId,senderId,country,price,quantity,total"
    )

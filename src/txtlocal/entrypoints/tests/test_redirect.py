from fastapi.testclient import TestClient

from txtlocal.entrypoints.redirect import app_of
from txtlocal.slices.analytics.model import TrackedLink
from txtlocal.slices.analytics.service import AnalyticsService
from txtlocal.slices.analytics.tests.fakes import (
    ACCOUNT_ID,
    NOW,
    FakeAnalyticsRepo,
    FakeClickQueries,
    FakeUsageQueries,
)


def service_over(repo: FakeAnalyticsRepo) -> AnalyticsService:
    return AnalyticsService(
        click_queries=FakeClickQueries(results=[]),
        clock=lambda: NOW,
        public_base_url="https://app.txtlocal.example",
        repo=repo,
        usage_queries=FakeUsageQueries(results=[]),
    )


def test_app_of_answers_404_for_an_unknown_code() -> None:
    client = TestClient(app_of(service_over(FakeAnalyticsRepo())))

    response = client.get("/l/ab3de5fgh7", follow_redirects=False)

    assert response.status_code == 404


def test_app_of_redirects_a_known_code() -> None:
    link = TrackedLink(
        account_id=ACCOUNT_ID,
        campaign_id="",
        clicks_total=0,
        code="ab3de5fgh7",
        created_at=NOW,
        last_rollup=None,
        url="https://example.com/target",
    )
    client = TestClient(app_of(service_over(FakeAnalyticsRepo(links={"ab3de5fgh7": link}))))

    response = client.get("/l/ab3de5fgh7", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "https://example.com/target"


def test_app_of_exposes_no_docs() -> None:
    client = TestClient(app_of(service_over(FakeAnalyticsRepo())))

    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404

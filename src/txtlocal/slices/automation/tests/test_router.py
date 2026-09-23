from http import HTTPStatus
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from txtlocal.shared.errors import BadRequest, NotFound, Unauthorized
from txtlocal.slices.automation.router import (
    OPERATOR_HEADER,
    OPERATOR_PREFIX,
    PREFIX,
    build_email_demo_router,
    build_operator_router,
    build_router,
)
from txtlocal.slices.automation.tests.fakes import (
    ACCOUNT,
    FakeSender,
    RecordingCampaigns,
    StubSenders,
)
from txtlocal.slices.identity.model import Principal, Role

if TYPE_CHECKING:
    from txtlocal.slices.automation.service import AutomationService

OPERATOR_SECRET = "operator-secret-value"
PRINCIPAL = Principal(
    account_id=ACCOUNT, role=Role.OWNER, user_id="user-1", username="demo@txtlocal.local"
)


async def fixed_principal(_request: Request) -> Principal:
    return PRINCIPAL


@pytest.fixture
def client(service: AutomationService) -> TestClient:
    app = FastAPI()
    app.include_router(build_router(service, fixed_principal))
    return TestClient(app)


@pytest.fixture
def operator_client(service: AutomationService) -> TestClient:
    app = FastAPI()
    app.include_router(build_operator_router(service, OPERATOR_SECRET))
    return TestClient(app)


@pytest.fixture
def demo_email_client(service: AutomationService) -> TestClient:
    app = FastAPI()
    app.include_router(build_email_demo_router(service))
    return TestClient(app)


def test_create_and_list_inbound_rules(client: TestClient) -> None:
    created = client.post(
        f"{PREFIX}/rules/inbound",
        json={"action": "SEND_TO_MESSENGER", "name": "Send to messenger"},
    )
    assert created.status_code == HTTPStatus.CREATED
    body = created.json()
    assert (body["action"], body["name"], body["matchKind"], body["ruleId"]) == (
        "SEND_TO_MESSENGER",
        "Send to messenger",
        "ANY",
        body["ruleId"],
    )

    listed = client.get(f"{PREFIX}/rules/inbound")
    assert listed.status_code == HTTPStatus.OK
    assert listed.json() == [body]


def test_update_and_delete_inbound_rule(client: TestClient) -> None:
    rule_id = client.post(
        f"{PREFIX}/rules/inbound", json={"action": "POLL", "name": "Vote", "matchKind": "ANY"}
    ).json()["ruleId"]

    updated = client.put(
        f"{PREFIX}/rules/inbound/{rule_id}",
        json={"action": "POLL", "name": "Vote", "enabled": False},
    )
    assert updated.status_code == HTTPStatus.OK
    assert updated.json()["enabled"] is False

    deleted = client.delete(f"{PREFIX}/rules/inbound/{rule_id}")
    assert deleted.status_code == HTTPStatus.NO_CONTENT

    with pytest.raises(NotFound):
        client.put(f"{PREFIX}/rules/inbound/{rule_id}", json={"action": "POLL", "name": "Vote"})


def test_create_delivery_rule_returns_the_secret_once(client: TestClient) -> None:
    created = client.post(
        f"{PREFIX}/rules/delivery", json={"name": "Report", "url": "https://example.com/report"}
    )
    assert created.status_code == HTTPStatus.CREATED
    body = created.json()
    assert body["secret"]
    assert "secret" not in body["rule"]

    listed = client.get(f"{PREFIX}/rules/delivery")
    assert listed.status_code == HTTPStatus.OK
    assert listed.json() == [body["rule"]]


def test_delivery_rule_refuses_a_non_https_url(client: TestClient) -> None:
    with pytest.raises(BadRequest):
        client.post(
            f"{PREFIX}/rules/delivery", json={"name": "Report", "url": "http://example.com"}
        )


def test_webhook_test_endpoint_answers_accepted(client: TestClient) -> None:
    rule_id = client.post(
        f"{PREFIX}/rules/delivery", json={"name": "Report", "url": "https://example.com/report"}
    ).json()["rule"]["ruleId"]

    response = client.post(f"{PREFIX}/webhooks/{rule_id}/test")

    assert response.status_code == HTTPStatus.ACCEPTED


def test_register_and_list_websites(client: TestClient) -> None:
    created = client.post(f"{PREFIX}/websites", json={"domains": ["junaid.guru"]})
    assert created.status_code == HTTPStatus.CREATED
    body = created.json()
    assert body == [
        {
            "domain": "junaid.guru",
            "registeredAt": body[0]["registeredAt"],
            "rejectedReason": None,
            "status": "UNDER_REVIEW",
        }
    ]

    listed = client.get(f"{PREFIX}/websites")
    assert listed.status_code == HTTPStatus.OK
    assert listed.json() == body


def test_register_websites_refuses_a_fourth_in_one_submission(client: TestClient) -> None:
    with pytest.raises(BadRequest):
        client.post(
            f"{PREFIX}/websites",
            json={"domains": ["a.example", "b.example", "c.example", "d.example"]},
        )


def test_add_and_remove_email_sender(client: TestClient, senders: StubSenders) -> None:
    senders.rows[ACCOUNT] = [FakeSender(sender_id="sender-1")]

    created = client.post(
        f"{PREFIX}/email-senders",
        json={"email": "a@example.com", "senderId": "sender-1", "userId": "user-1"},
    )
    assert created.status_code == HTTPStatus.CREATED
    body = created.json()
    assert body == {"email": "a@example.com", "senderId": "sender-1", "userId": "user-1"}

    listed = client.get(f"{PREFIX}/email-senders")
    assert listed.json() == [body]

    removed = client.delete(f"{PREFIX}/email-senders/a@example.com")
    assert removed.status_code == HTTPStatus.NO_CONTENT

    with pytest.raises(NotFound):
        client.delete(f"{PREFIX}/email-senders/a@example.com")


def test_operator_can_approve_a_website_without_the_24_hour_wait(
    client: TestClient, operator_client: TestClient
) -> None:
    client.post(f"{PREFIX}/websites", json={"domains": ["junaid.guru"]})

    response = operator_client.post(
        f"{OPERATOR_PREFIX}/accounts/{ACCOUNT}/websites/junaid.guru/approve",
        headers={OPERATOR_HEADER: OPERATOR_SECRET},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["status"] == "APPROVED"


def test_operator_can_reject_a_website_with_a_reason(
    client: TestClient, operator_client: TestClient
) -> None:
    client.post(f"{PREFIX}/websites", json={"domains": ["junaid.guru"]})

    response = operator_client.post(
        f"{OPERATOR_PREFIX}/accounts/{ACCOUNT}/websites/junaid.guru/reject",
        headers={OPERATOR_HEADER: OPERATOR_SECRET},
        json={"reason": "Looks unsafe"},
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert (body["status"], body["rejectedReason"]) == ("REJECTED", "Looks unsafe")


def test_operator_endpoint_refuses_a_missing_secret(operator_client: TestClient) -> None:
    with pytest.raises(Unauthorized):
        operator_client.post(f"{OPERATOR_PREFIX}/accounts/{ACCOUNT}/websites/junaid.guru/approve")


def test_operator_endpoint_refuses_the_wrong_secret(operator_client: TestClient) -> None:
    with pytest.raises(Unauthorized):
        operator_client.post(
            f"{OPERATOR_PREFIX}/accounts/{ACCOUNT}/websites/junaid.guru/approve",
            headers={OPERATOR_HEADER: "wrong-secret"},
        )


def test_operator_endpoint_refuses_an_empty_secret_when_none_is_configured(
    service: AutomationService,
) -> None:
    app = FastAPI()
    app.include_router(build_operator_router(service, ""))

    with pytest.raises(Unauthorized):
        TestClient(app).post(
            f"{OPERATOR_PREFIX}/accounts/{ACCOUNT}/websites/junaid.guru/approve",
            headers={OPERATOR_HEADER: ""},
        )


def test_demo_inbound_email_reaches_the_service(
    client: TestClient,
    demo_email_client: TestClient,
    campaigns: RecordingCampaigns,
    senders: StubSenders,
) -> None:
    senders.rows[ACCOUNT] = [FakeSender(sender_id="sender-1")]
    client.post(
        f"{PREFIX}/email-senders",
        json={"email": "jan@example.com", "senderId": "sender-1", "userId": "user-9"},
    )

    response = demo_email_client.post(
        "/api/app/demo/inbound-email",
        json={"body": "hi", "numbers": ["+447984390718"], "senderEmail": "jan@example.com"},
    )

    assert response.status_code == HTTPStatus.ACCEPTED
    [(principal, request, _now)] = campaigns.calls
    assert (principal.account_id, principal.user_id, request.sender_id) == (
        ACCOUNT,
        "user-9",
        "sender-1",
    )

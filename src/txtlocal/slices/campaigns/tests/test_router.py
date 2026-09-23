from datetime import timedelta
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from txtlocal.shared.errors import Conflict, NotFound
from txtlocal.slices.campaigns.model import CampaignStatus, OptOutMode
from txtlocal.slices.campaigns.repo import PAGE_SIZE
from txtlocal.slices.campaigns.router import build_public_router, build_router
from txtlocal.slices.campaigns.service import (
    CAMPAIGN_NOT_FOUND,
    CAMPAIGN_SENDING,
    UNKNOWN_LINK,
    UNSUBSCRIBED_PAGE,
    unsubscribe_token,
)
from txtlocal.slices.campaigns.tests.fakes import (
    ACCOUNT_ID,
    BODY,
    GB_ONE,
    GB_TWO,
    LIST_ID,
    NOW,
    PRINCIPAL,
    SECRET,
    World,
    contact,
    contacts_of,
    draft_campaign,
    list_campaign,
    world,
)
from txtlocal.slices.messaging.model import Product

if TYPE_CHECKING:
    from txtlocal.slices.identity.model import Principal

CAMPAIGNS = "/api/app/campaigns"


async def authenticated(_request: Request) -> Principal:
    return PRINCIPAL


def client_of(w: World) -> TestClient:
    app = FastAPI()
    app.include_router(build_router(w.service, authenticated))
    app.include_router(build_public_router(w.service))
    return TestClient(app)


def seeded(w: World, count: int) -> list[str]:
    campaigns = [draft_campaign() for _ in range(count)]
    for campaign in campaigns:
        w.repo.rows[(ACCOUNT_ID, campaign.campaign_id)] = campaign
    return [campaign.campaign_id for campaign in campaigns]


def test_list_answers_a_camel_case_page() -> None:
    w = world()
    (campaign_id,) = seeded(w, 1)
    campaign = w.repo.rows[(ACCOUNT_ID, campaign_id)]

    body = client_of(w).get(CAMPAIGNS).json()
    assert body == {"cursor": None, "items": [campaign.model_dump(mode="json")]}


def test_list_follows_the_cursor() -> None:
    w = world()
    ids = seeded(w, PAGE_SIZE + 1)
    client = client_of(w)

    first = client.get(CAMPAIGNS).json()
    second = client.get(CAMPAIGNS, params={"cursor": first["cursor"]}).json()
    assert (
        [item["campaignId"] for item in first["items"]],
        [item["campaignId"] for item in second["items"]],
        second["cursor"],
    ) == (ids[:0:-1], [ids[0]], None)


@pytest.mark.parametrize(
    ("params", "found"),
    [
        ({"kind": Product.SMS}, 1),
        ({"kind": Product.MMS}, 0),
        ({"q": "Quick SMS"}, 1),
        ({"q": "Helloworld"}, 0),
    ],
    ids=["product-matches", "product-excludes", "search-matches", "search-excludes"],
)
def test_list_filters_the_page(params: dict[str, str], found: int) -> None:
    w = world()
    seeded(w, 1)
    body = client_of(w).get(CAMPAIGNS, params=params).json()
    assert len(body["items"]) == found


def test_get_answers_the_campaign() -> None:
    w = world()
    (campaign_id,) = seeded(w, 1)
    assert client_of(w).get(f"{CAMPAIGNS}/{campaign_id}").json()["campaignId"] == campaign_id


def test_get_refuses_an_unknown_campaign() -> None:
    with pytest.raises(NotFound) as caught:
        client_of(world()).get(f"{CAMPAIGNS}/missing")
    assert str(caught.value) == CAMPAIGN_NOT_FOUND


def test_create_answers_the_new_draft() -> None:
    w = world()
    response = client_of(w).post(
        CAMPAIGNS, json={"body": BODY, "listId": LIST_ID, "name": "Helloworld"}
    )
    assert (response.status_code, response.json()["status"]) == (201, CampaignStatus.DRAFT)


def test_save_answers_the_stored_draft() -> None:
    w = world()
    campaign = list_campaign()
    w.repo.rows[(ACCOUNT_ID, campaign.campaign_id)] = campaign

    body = (
        client_of(w)
        .put(
            f"{CAMPAIGNS}/{campaign.campaign_id}",
            json={"body": "Changed", "listId": LIST_ID, "name": "Renamed"},
        )
        .json()
    )
    assert (body["body"], body["name"]) == ("Changed", "Renamed")


def test_delete_answers_no_content() -> None:
    w = world()
    campaign = list_campaign()
    w.repo.rows[(ACCOUNT_ID, campaign.campaign_id)] = campaign

    assert client_of(w).delete(f"{CAMPAIGNS}/{campaign.campaign_id}").status_code == 204


def test_quote_answers_the_confirmation_numbers() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE), contact(GB_TWO)]))
    campaign = list_campaign()
    w.repo.rows[(ACCOUNT_ID, campaign.campaign_id)] = campaign

    body = client_of(w).post(f"{CAMPAIGNS}/{campaign.campaign_id}/quote").json()
    assert body == {
        "costMicro": 85_400,
        "parts": 1,
        "recipients": 2,
        "senderDisplay": "Shared Number",
    }


def test_schedule_takes_a_send_at() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = list_campaign()
    w.repo.rows[(ACCOUNT_ID, campaign.campaign_id)] = campaign
    send_at = NOW + timedelta(hours=1)

    body = (
        client_of(w)
        .post(
            f"{CAMPAIGNS}/{campaign.campaign_id}/schedule",
            json={"sendAt": send_at.isoformat()},
        )
        .json()
    )
    assert (body["status"], body["scheduledAt"]) == (
        CampaignStatus.SCHEDULED,
        "2026-09-19T13:00:00.000Z",
    )


def test_schedule_now_sends_at_the_current_time() -> None:
    w = world(contacts=contacts_of([contact(GB_ONE)]))
    campaign = list_campaign()
    w.repo.rows[(ACCOUNT_ID, campaign.campaign_id)] = campaign

    body = (
        client_of(w).post(f"{CAMPAIGNS}/{campaign.campaign_id}/schedule", json={"now": True}).json()
    )
    assert body["scheduledAt"] == "2026-09-19T12:00:00.000Z"


def test_cancel_while_sending_answers_the_conflict_sentence() -> None:
    w = world()
    campaign = list_campaign(status=CampaignStatus.SENDING)
    w.repo.rows[(ACCOUNT_ID, campaign.campaign_id)] = campaign

    with pytest.raises(Conflict) as caught:
        client_of(w).post(f"{CAMPAIGNS}/{campaign.campaign_id}/cancel")
    assert str(caught.value) == CAMPAIGN_SENDING


def test_duplicate_answers_a_new_draft() -> None:
    w = world()
    campaign = list_campaign()
    w.repo.rows[(ACCOUNT_ID, campaign.campaign_id)] = campaign

    body = client_of(w).post(f"{CAMPAIGNS}/{campaign.campaign_id}/duplicate").json()
    assert (body["name"], body["status"]) == ("Helloworld (copy)", CampaignStatus.DRAFT)


def test_report_answers_the_campaign_with_zero_clicks() -> None:
    w = world()
    campaign = list_campaign(opt_out_mode=OptOutMode.REPLY_STOP)
    w.repo.rows[(ACCOUNT_ID, campaign.campaign_id)] = campaign

    body = client_of(w).get(f"{CAMPAIGNS}/{campaign.campaign_id}/report").json()
    assert body == {"campaign": campaign.model_dump(mode="json"), "clicks": 0}


def test_unsubscribe_answers_the_plain_page() -> None:
    w = world()
    token = unsubscribe_token(SECRET, ACCOUNT_ID, GB_ONE)

    response = client_of(w).get(f"/api/u/{token}")
    assert (response.status_code, response.text) == (200, UNSUBSCRIBED_PAGE)


def test_unsubscribe_refuses_an_unknown_token() -> None:
    with pytest.raises(NotFound) as caught:
        client_of(world()).get("/api/u/nonsense")
    assert str(caught.value) == UNKNOWN_LINK

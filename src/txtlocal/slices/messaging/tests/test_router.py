from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from txtlocal.shared.errors import BadRequest, NotFound
from txtlocal.slices.campaigns.model import QuickQuote, QuickSendResult
from txtlocal.slices.messaging.gateway import LocalMediaStorage, MediaStorage
from txtlocal.slices.messaging.model import MessageStatus, Product, QuickSendRequest
from txtlocal.slices.messaging.router import build_router
from txtlocal.slices.messaging.service import (
    MEDIA_NOT_FOUND,
    MEDIA_TYPE_MESSAGE,
    MESSAGE_NOT_FOUND,
    RANGE_INVERTED,
    TEMPLATE_NOT_FOUND,
)
from txtlocal.slices.messaging.tests.support import (
    DESTINATION,
    NOW,
    PRINCIPAL,
    InMemoryMessagingRepo,
    RecordingGateway,
    build_service,
    row_at,
)

if TYPE_CHECKING:
    from txtlocal.slices.identity.model import Principal

HTTP_OK = 200
HTTP_CREATED = 201
HTTP_NO_CONTENT = 204
HTTP_UNPROCESSABLE = 422


class QuickSendStub:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Principal, QuickSendRequest, datetime]] = []

    async def quote_quick(
        self, principal: Principal, request: QuickSendRequest, now: datetime
    ) -> QuickQuote:
        self.calls.append(("quote", principal, request, now))
        return QuickQuote(cost_micro=0, parts=1, recipients=len(request.to), refused=[])

    async def send_quick(
        self, principal: Principal, request: QuickSendRequest, now: datetime
    ) -> QuickSendResult:
        self.calls.append(("send", principal, request, now))
        return QuickSendResult(
            campaign_id="camp-1", cost_micro=0, recipients=len(request.to), refused=[]
        )


async def authenticated(request: Request) -> Principal:
    assert request.method
    return PRINCIPAL


def client(
    media: MediaStorage | None = None,
) -> tuple[TestClient, InMemoryMessagingRepo, QuickSendStub]:
    repo = InMemoryMessagingRepo()
    quick_send = QuickSendStub()
    service = build_service(repo, RecordingGateway(clock=lambda: NOW), media=media)
    app = FastAPI()
    app.include_router(build_router(service, authenticated, quick_send))
    return TestClient(app), repo, quick_send


def test_quote_delegates_to_the_quick_send_port() -> None:
    api, _, quick_send = client()

    response = api.post("/api/app/messages/quote", json={"to": [DESTINATION], "body": "Hi"})

    kind, principal, request, now = quick_send.calls[0]
    assert (response.status_code, response.json()["recipients"]) == (HTTP_OK, 1)
    assert (kind, principal, now) == ("quote", PRINCIPAL, NOW)
    assert request == QuickSendRequest(body="Hi", to=[DESTINATION])


def test_send_delegates_to_the_quick_send_port() -> None:
    api, _, quick_send = client()

    response = api.post(
        "/api/app/messages/send",
        json={"to": [DESTINATION], "body": "Hi", "kind": "MMS", "shortenUrls": True},
    )

    kind, _, request, _ = quick_send.calls[0]
    assert (response.status_code, response.json()["campaignId"]) == (HTTP_OK, "camp-1")
    assert (kind, request.kind, request.shorten_urls) == ("send", Product.MMS, True)


def test_history_answers_a_page_from_the_query_string() -> None:
    api, repo, _ = client()
    hit = row_at(NOW, 1)
    repo.seed(hit, row_at(NOW - timedelta(minutes=1), 2, to="+447400123106"))

    response = api.get(
        "/api/app/messages",
        params={
            "from": "2026-09-12",
            "to": "2026-09-19",
            "field": "TO",
            "q": DESTINATION,
            "kind": "SMS",
        },
    )

    body = response.json()
    assert response.status_code == HTTP_OK
    assert body["cursor"] is None
    assert [item["messageId"] for item in body["items"]] == [hit.message_id]
    assert (body["items"][0]["from"], body["items"][0]["to"], body["items"][0]["status"]) == (
        "SHARED",
        DESTINATION,
        MessageStatus.QUEUED,
    )


def test_history_refusals_surface_as_bad_request() -> None:
    api, _, _ = client()

    with pytest.raises(BadRequest) as caught:
        api.get("/api/app/messages", params={"from": "2026-09-19", "to": "2026-09-18"})

    assert str(caught.value) == RANGE_INVERTED


def test_export_streams_csv_as_an_attachment() -> None:
    api, repo, _ = client()
    repo.seed(row_at(NOW))

    response = api.get("/api/app/messages/export")

    assert response.status_code == HTTP_OK
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == 'attachment; filename="sms-history.csv"'
    assert response.text.splitlines()[0] == "username,date,from,to,status,body"
    assert len(response.text.splitlines()) == 2


def test_detail_answers_the_row() -> None:
    api, repo, _ = client()
    row = row_at(NOW)
    repo.seed(row)

    response = api.get(f"/api/app/messages/{row.message_id}")

    assert (response.status_code, response.json()["messageId"]) == (HTTP_OK, row.message_id)


def test_detail_of_an_unknown_message_is_not_found() -> None:
    api, _, _ = client()

    with pytest.raises(NotFound) as caught:
        api.get("/api/app/messages/not-a-uuid")

    assert str(caught.value) == MESSAGE_NOT_FOUND


def test_templates_round_trip_through_the_endpoints() -> None:
    api, _, _ = client()

    created = api.post("/api/app/templates", json={"name": "Greeting", "body": "Hi"})
    template_id = created.json()["templateId"]
    edited = api.put(
        f"/api/app/templates/{template_id}", json={"name": "Greeting v2", "body": "Hello"}
    )
    listed = api.get("/api/app/templates")
    deleted = api.delete(f"/api/app/templates/{template_id}")

    assert (created.status_code, edited.status_code, deleted.status_code) == (
        HTTP_CREATED,
        HTTP_OK,
        HTTP_NO_CONTENT,
    )
    assert [template["name"] for template in listed.json()] == ["Greeting v2"]
    assert api.get("/api/app/templates").json() == []


def test_update_of_an_unknown_template_is_not_found() -> None:
    api, _, _ = client()

    with pytest.raises(NotFound) as caught:
        api.put("/api/app/templates/missing", json={"name": "x", "body": "y"})

    assert str(caught.value) == TEMPLATE_NOT_FOUND


@pytest.mark.parametrize(
    ("name_length", "status"),
    [(100, HTTP_CREATED), (101, HTTP_UNPROCESSABLE)],
    ids=["hundred-character-name-is-accepted", "hundred-and-first-character-is-refused"],
)
def test_template_name_ceiling(name_length: int, status: int) -> None:
    api, _, _ = client()

    response = api.post("/api/app/templates", json={"name": "n" * name_length, "body": "Hi"})

    assert response.status_code == status


def test_create_media_upload_answers_a_key_and_a_put_url(tmp_path: Path) -> None:
    api, _, _ = client(LocalMediaStorage(directory=tmp_path, site="https://txtlocal.test"))

    response = api.post("/api/app/messaging/media", json={"contentType": "image/png"})

    body = response.json()
    assert response.status_code == HTTP_OK
    assert body["key"].endswith(".png")
    assert body["uploadUrl"] == f"https://txtlocal.test/api/app/messaging/media/{body['key']}"


def test_create_media_upload_refuses_an_unsupported_content_type(tmp_path: Path) -> None:
    api, _, _ = client(LocalMediaStorage(directory=tmp_path, site="https://txtlocal.test"))

    with pytest.raises(BadRequest) as caught:
        api.post("/api/app/messaging/media", json={"contentType": "application/pdf"})
    assert str(caught.value) == MEDIA_TYPE_MESSAGE


def test_media_is_readable_at_the_url_it_was_uploaded_to(tmp_path: Path) -> None:
    api, _, _ = client(LocalMediaStorage(directory=tmp_path, site="https://txtlocal.test"))
    key = api.post("/api/app/messaging/media", json={"contentType": "image/png"}).json()["key"]

    put = api.put(
        f"/api/app/messaging/media/{key}", content=b"pixels", headers={"content-type": "image/png"}
    )
    got = api.get(f"/api/app/messaging/media/{key}")

    assert put.status_code == HTTP_NO_CONTENT
    assert (got.status_code, got.content, got.headers["content-type"]) == (
        HTTP_OK,
        b"pixels",
        "image/png",
    )


def test_reading_an_unknown_media_key_is_not_found(tmp_path: Path) -> None:
    api, _, _ = client(LocalMediaStorage(directory=tmp_path, site="https://txtlocal.test"))

    with pytest.raises(NotFound) as caught:
        api.get("/api/app/messaging/media/00000000-0000-7000-8000-000000000000.png")
    assert str(caught.value) == MEDIA_NOT_FOUND

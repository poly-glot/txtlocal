from http import HTTPStatus

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from txtlocal.shared.errors import AppError, BadRequest, Conflict, NotFound
from txtlocal.shared.phone import INVALID_NUMBER_MESSAGE
from txtlocal.slices.contacts.router import PREFIX, build_router
from txtlocal.slices.contacts.service import (
    CONTACT_NOT_FOUND,
    EXAMPLE_LIST,
    LIST_NOT_FOUND,
    OPT_OUT_LIST,
    OPT_OUT_NOT_DELETABLE,
    OPT_OUT_NOT_RENAMABLE,
    ContactsService,
)
from txtlocal.slices.contacts.tests.fakes import ACCOUNT, OWNER_MOBILE, SECOND_MOBILE
from txtlocal.slices.identity.model import Principal, Role

PRINCIPAL = Principal(
    account_id=ACCOUNT, role=Role.OWNER, user_id="user-1", username="demo@txtlocal.local"
)
TIMESTAMP = "2026-09-19T12:00:00.000Z"


async def fixed_principal(_request: Request) -> Principal:
    return PRINCIPAL


@pytest.fixture
def client(provisioned: ContactsService) -> TestClient:
    app = FastAPI()
    app.include_router(build_router(provisioned, fixed_principal))
    return TestClient(app)


def lists_of(client: TestClient) -> list[dict[str, object]]:
    response = client.get(f"{PREFIX}/lists")
    assert response.status_code == HTTPStatus.OK
    body: list[dict[str, object]] = response.json()
    return body


def list_id_of(client: TestClient, name: str) -> str:
    return str(next(one for one in lists_of(client) if one["name"] == name)["listId"])


def contacts_of(client: TestClient, list_id: str) -> dict[str, object]:
    response = client.get(f"{PREFIX}/lists/{list_id}/contacts")
    assert response.status_code == HTTPStatus.OK
    body: dict[str, object] = response.json()
    return body


def test_get_lists_answers_a_card_per_list_with_its_count(client: TestClient) -> None:
    body = lists_of(client)

    assert body == [
        {
            "contactCount": 1,
            "createdAt": TIMESTAMP,
            "kind": "STANDARD",
            "listId": body[0]["listId"],
            "name": EXAMPLE_LIST,
        },
        {
            "contactCount": 0,
            "createdAt": TIMESTAMP,
            "kind": "OPT_OUT",
            "listId": body[1]["listId"],
            "name": OPT_OUT_LIST,
        },
    ]


def test_get_contacts_answers_a_page_of_rows(client: TestClient) -> None:
    list_id = list_id_of(client, EXAMPLE_LIST)

    body = contacts_of(client, list_id)

    assert body == {
        "cursor": None,
        "items": [
            {
                "accountId": ACCOUNT,
                "cf1": "",
                "cf2": "",
                "cf3": "",
                "cf4": "",
                "email": "demo@txtlocal.local",
                "firstName": "Sam",
                "lastName": "Jones",
                "listId": list_id,
                "mobile": OWNER_MOBILE,
                "updatedAt": TIMESTAMP,
            }
        ],
    }


def test_post_lists_answers_created(client: TestClient) -> None:
    response = client.post(f"{PREFIX}/lists", json={"name": "Leads"})

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["name"] == "Leads"


def test_post_contacts_answers_created_with_the_normalised_mobile(client: TestClient) -> None:
    list_id = list_id_of(client, EXAMPLE_LIST)

    response = client.post(
        f"{PREFIX}/lists/{list_id}/contacts", json={"firstName": "Ada", "mobile": "07411 972300"}
    )

    assert response.status_code == HTTPStatus.CREATED
    assert response.json()["mobile"] == SECOND_MOBILE


def test_patch_contact_addresses_the_row_by_its_mobile(client: TestClient) -> None:
    list_id = list_id_of(client, EXAMPLE_LIST)

    response = client.patch(
        f"{PREFIX}/lists/{list_id}/contacts/{OWNER_MOBILE}",
        json={"firstName": "Renamed", "mobile": OWNER_MOBILE},
    )

    assert response.status_code == HTTPStatus.OK
    assert response.json()["firstName"] == "Renamed"


def test_delete_contact_answers_no_content(client: TestClient) -> None:
    list_id = list_id_of(client, EXAMPLE_LIST)

    response = client.delete(f"{PREFIX}/lists/{list_id}/contacts/{OWNER_MOBILE}")

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert contacts_of(client, list_id)["items"] == []


def test_post_import_answers_the_report_sentence(client: TestClient) -> None:
    list_id = list_id_of(client, EXAMPLE_LIST)

    response = client.post(
        f"{PREFIX}/lists/{list_id}/contacts/import",
        json={"rows": [{"mobile": SECOND_MOBILE}, {"mobile": "nope"}]},
    )

    assert response.json() == {
        "imported": 1,
        "message": "Imported 1, updated 0, skipped 1 invalid",
        "skipped": 1,
        "updated": 0,
    }


def test_post_bulk_answers_what_it_removed(client: TestClient) -> None:
    list_id = list_id_of(client, EXAMPLE_LIST)

    response = client.post(
        f"{PREFIX}/lists/{list_id}/contacts/bulk",
        json={"action": "DELETE", "contactIds": [OWNER_MOBILE]},
    )

    assert response.json() == {"message": "Removed 1 contact", "removed": 1}


def test_post_clean_up_answers_what_it_removed(client: TestClient) -> None:
    list_id = list_id_of(client, EXAMPLE_LIST)

    response = client.post(f"{PREFIX}/lists/{list_id}/clean-up", json={"action": "INVALID"})

    assert response.json() == {"message": "Removed 0 contacts", "removed": 0}


def test_get_export_answers_a_csv_attachment(client: TestClient) -> None:
    list_id = list_id_of(client, EXAMPLE_LIST)

    response = client.get(f"{PREFIX}/lists/{list_id}/export")

    assert response.headers["content-disposition"] == 'attachment; filename="contacts.csv"'
    assert response.text == (
        "mobile,first_name,last_name,email,cf1,cf2,cf3,cf4\n"
        f"{OWNER_MOBILE},Sam,Jones,demo@txtlocal.local,,,,\n"
    )


def test_get_search_answers_the_autocomplete_hits(client: TestClient) -> None:
    response = client.get(f"{PREFIX}/contacts/search", params={"limit": 5, "q": "Sam"})

    assert response.json() == [
        {
            "firstName": "Sam",
            "lastName": "Jones",
            "listId": list_id_of(client, EXAMPLE_LIST),
            "mobile": OWNER_MOBILE,
        }
    ]


def test_get_search_without_a_query_answers_nothing(client: TestClient) -> None:
    response = client.get(f"{PREFIX}/contacts/search")

    assert response.json() == []


@pytest.mark.parametrize(
    ("method", "path", "json", "error", "message"),
    [
        ("PATCH", "/lists/{optOut}", {"name": "Blocked"}, Conflict, OPT_OUT_NOT_RENAMABLE),
        ("DELETE", "/lists/{optOut}", None, Conflict, OPT_OUT_NOT_DELETABLE),
        ("GET", "/lists/missing/contacts", None, NotFound, LIST_NOT_FOUND),
        (
            "POST",
            "/lists/{example}/contacts",
            {"mobile": "nope"},
            BadRequest,
            INVALID_NUMBER_MESSAGE,
        ),
        (
            "DELETE",
            "/lists/{example}/contacts/+447411972300",
            None,
            NotFound,
            CONTACT_NOT_FOUND,
        ),
    ],
    ids=[
        "rename-opt-out-list",
        "delete-opt-out-list",
        "page-an-unknown-list",
        "add-an-unparseable-number",
        "delete-a-contact-the-list-does-not-hold",
    ],
)
def test_refusals_carry_their_copy(
    client: TestClient,
    method: str,
    path: str,
    json: dict[str, str] | None,
    error: type[AppError],
    message: str,
) -> None:
    ids = {
        "example": list_id_of(client, EXAMPLE_LIST),
        "optOut": list_id_of(client, OPT_OUT_LIST),
    }

    with pytest.raises(error) as caught:
        client.request(method, f"{PREFIX}{path.format(**ids)}", json=json)

    assert str(caught.value) == message

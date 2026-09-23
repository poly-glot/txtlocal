from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Path, Request, Response, params

from txtlocal.slices.contacts.model import (
    ActionResult,
    BulkRequest,
    CleanUpRequest,
    Contact,
    ContactHit,
    ContactInput,
    ContactList,
    ContactPage,
    ImportReport,
    ImportRequest,
    ListRequest,
)
from txtlocal.slices.contacts.service import PAGE_SIZE, SEARCH_LIMIT

if TYPE_CHECKING:
    from txtlocal.slices.contacts.service import ContactsService
    from txtlocal.slices.identity.model import Principal

type Authenticated = Callable[[Request], Awaitable[Principal]]
type Caller = params.Depends

CSV_MEDIA_TYPE = "text/csv"
CSV_RESPONSES: dict[int | str, dict[str, object]] = {
    HTTPStatus.OK: {"content": {CSV_MEDIA_TYPE: {"schema": {"type": "string"}}}}
}
EXPORT_DISPOSITION = 'attachment; filename="contacts.csv"'
PREFIX = "/api/app"


def build_router(service: ContactsService, authenticated: Authenticated) -> APIRouter:
    router = APIRouter(prefix=PREFIX)
    caller = Depends(authenticated)

    list_routes(router, service, caller)
    contact_routes(router, service, caller)
    search_routes(router, service, caller)
    return router


def list_routes(router: APIRouter, service: ContactsService, caller: Caller) -> None:
    @router.get("/lists", response_model=list[ContactList])
    async def lists(
        principal: Annotated[Principal, caller], q: str | None = None
    ) -> list[ContactList]:
        return await service.lists(principal.account_id, q)

    @router.post("/lists", response_model=ContactList, status_code=HTTPStatus.CREATED)
    async def create_list(
        principal: Annotated[Principal, caller], request: ListRequest
    ) -> ContactList:
        return await service.create_list(principal.account_id, request)

    @router.patch("/lists/{listId}", response_model=ContactList)
    async def rename_list(
        principal: Annotated[Principal, caller],
        list_id: Annotated[str, Path(alias="listId")],
        request: ListRequest,
    ) -> ContactList:
        return await service.rename_list(principal.account_id, list_id, request)

    @router.delete("/lists/{listId}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_list(
        principal: Annotated[Principal, caller],
        list_id: Annotated[str, Path(alias="listId")],
    ) -> None:
        await service.delete_list(principal.account_id, list_id)

    @router.post("/lists/{listId}/clean-up", response_model=ActionResult)
    async def clean_up(
        principal: Annotated[Principal, caller],
        list_id: Annotated[str, Path(alias="listId")],
        request: CleanUpRequest,
    ) -> ActionResult:
        return await service.clean_up(principal.account_id, list_id, request)

    @router.get("/lists/{listId}/export", response_class=Response, responses=CSV_RESPONSES)
    async def export(
        principal: Annotated[Principal, caller],
        list_id: Annotated[str, Path(alias="listId")],
    ) -> Response:
        return Response(
            content=await service.export(principal.account_id, list_id),
            headers={"Content-Disposition": EXPORT_DISPOSITION},
            media_type=CSV_MEDIA_TYPE,
        )


def contact_routes(router: APIRouter, service: ContactsService, caller: Caller) -> None:
    @router.get("/lists/{listId}/contacts", response_model=ContactPage)
    async def contacts(
        principal: Annotated[Principal, caller],
        list_id: Annotated[str, Path(alias="listId")],
        cursor: str | None = None,
        limit: int = PAGE_SIZE,
        q: str | None = None,
    ) -> ContactPage:
        return await service.contacts(principal.account_id, list_id, q, cursor, limit)

    @router.post("/lists/{listId}/contacts", response_model=Contact, status_code=HTTPStatus.CREATED)
    async def add_contact(
        principal: Annotated[Principal, caller],
        list_id: Annotated[str, Path(alias="listId")],
        request: ContactInput,
    ) -> Contact:
        return await service.add_contact(principal.account_id, list_id, request)

    @router.post("/lists/{listId}/contacts/import", response_model=ImportReport)
    async def import_contacts(
        principal: Annotated[Principal, caller],
        list_id: Annotated[str, Path(alias="listId")],
        request: ImportRequest,
    ) -> ImportReport:
        return await service.import_contacts(principal.account_id, list_id, request)

    @router.post("/lists/{listId}/contacts/bulk", response_model=ActionResult)
    async def bulk(
        principal: Annotated[Principal, caller],
        list_id: Annotated[str, Path(alias="listId")],
        request: BulkRequest,
    ) -> ActionResult:
        return await service.bulk(principal.account_id, list_id, request)

    @router.patch("/lists/{listId}/contacts/{contactId}", response_model=Contact)
    async def update_contact(
        principal: Annotated[Principal, caller],
        list_id: Annotated[str, Path(alias="listId")],
        contact_id: Annotated[str, Path(alias="contactId")],
        request: ContactInput,
    ) -> Contact:
        return await service.update_contact(principal.account_id, list_id, contact_id, request)

    @router.delete("/lists/{listId}/contacts/{contactId}", status_code=HTTPStatus.NO_CONTENT)
    async def remove_contact(
        principal: Annotated[Principal, caller],
        list_id: Annotated[str, Path(alias="listId")],
        contact_id: Annotated[str, Path(alias="contactId")],
    ) -> None:
        await service.remove_contact(principal.account_id, list_id, contact_id)


def search_routes(router: APIRouter, service: ContactsService, caller: Caller) -> None:
    @router.get("/contacts/search", response_model=list[ContactHit])
    async def search(
        principal: Annotated[Principal, caller], q: str = "", limit: int = SEARCH_LIMIT
    ) -> list[ContactHit]:
        return await service.search(principal.account_id, q, limit)

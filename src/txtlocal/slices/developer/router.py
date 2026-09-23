import json
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Header, Path, Query, Request, params, status
from fastapi.responses import JSONResponse

from txtlocal.shared.errors import BadRequest, Conflict
from txtlocal.slices.developer.model import (
    DEFAULT_LIMIT,
    DeveloperGeneral,
    IdempotencyStatus,
    LogFilters,
    LogsPage,
    V3Account,
    V3Balance,
    V3ContactBatch,
    V3ContactBatchResult,
    V3ContactCreated,
    V3ContactInput,
    V3ContactPage,
    V3HistoryMessage,
    V3HistoryPage,
    V3HistoryQuery,
    V3List,
    V3ListRequest,
    V3MmsSendRequest,
    V3SenderIdsResponse,
    V3SendRequest,
    V3SendResponse,
    V3TemplatesResponse,
)

if TYPE_CHECKING:
    from txtlocal.shared.model import Model
    from txtlocal.slices.developer.service import DeveloperService
    from txtlocal.slices.identity.model import Principal

type Authenticated = Callable[[Request], Awaitable[Principal]]
type Caller = params.Depends
type IdempotencyKeyHeader = Annotated[str | None, Header(alias="Idempotency-Key")]

APP_PREFIX = "/api/app/developer"
V3_PREFIX = "/api/v3"

MAX_IDEMPOTENCY_KEY = 64
IDEMPOTENCY_KEY_LENGTH_MESSAGE = "Idempotency-Key must be 1 to 64 characters"
IDEMPOTENCY_IN_PROGRESS_MESSAGE = "A request with this Idempotency-Key is in progress"
REPLAYED_HEADER = "Idempotent-Replayed"


async def idempotent[T: Model](
    service: DeveloperService,
    principal: Principal,
    idempotency_key: str | None,
    status_code: int,
    work: Callable[[], Awaitable[T]],
) -> T | JSONResponse:
    if idempotency_key is None:
        return await work()
    if not 1 <= len(idempotency_key) <= MAX_IDEMPOTENCY_KEY:
        raise BadRequest(IDEMPOTENCY_KEY_LENGTH_MESSAGE)

    now = service.clock()
    if not await service.begin_idempotency(principal.user_id, idempotency_key, now):
        existing = await service.peek_idempotency(principal.user_id, idempotency_key)
        if existing is None or existing.status is IdempotencyStatus.IN_FLIGHT:
            raise Conflict(IDEMPOTENCY_IN_PROGRESS_MESSAGE)

        return JSONResponse(
            content=json.loads(existing.response_body or "{}"),
            headers={REPLAYED_HEADER: "true"},
            status_code=existing.response_status or status_code,
        )

    result = await work()
    await service.finish_idempotency(
        principal.user_id, idempotency_key, status_code, result.model_dump_json(by_alias=True)
    )
    return result


def build_public_router(service: DeveloperService, api_user: Authenticated) -> APIRouter:
    router = APIRouter(prefix=V3_PREFIX)
    caller = Depends(api_user)
    sms_routes(router, service, caller)
    mms_routes(router, service, caller)
    account_routes(router, service, caller)
    list_routes(router, service, caller)
    contact_routes(router, service, caller)
    catalogue_routes(router, service, caller)
    return router


def sms_routes(router: APIRouter, service: DeveloperService, caller: Caller) -> None:
    @router.post("/sms/send", response_model=None, status_code=status.HTTP_201_CREATED)
    async def send(
        principal: Annotated[Principal, caller],
        request: V3SendRequest,
        idempotency_key: IdempotencyKeyHeader = None,
    ) -> V3SendResponse | JSONResponse:
        return await idempotent(
            service,
            principal,
            idempotency_key,
            status.HTTP_201_CREATED,
            lambda: service.send(principal, request, service.clock()),
        )

    @router.get("/sms/history", response_model=V3HistoryPage)
    async def history(
        principal: Annotated[Principal, caller], query: Annotated[V3HistoryQuery, Query()]
    ) -> V3HistoryPage:
        return await service.history(principal, query, service.clock())

    @router.get("/sms/{messageId}", response_model=V3HistoryMessage)
    async def detail(
        principal: Annotated[Principal, caller],
        message_id: Annotated[str, Path(alias="messageId")],
    ) -> V3HistoryMessage:
        return await service.detail(principal, message_id)


def mms_routes(router: APIRouter, service: DeveloperService, caller: Caller) -> None:
    @router.post("/mms/send", response_model=None, status_code=status.HTTP_201_CREATED)
    async def send_mms(
        principal: Annotated[Principal, caller],
        request: V3MmsSendRequest,
        idempotency_key: IdempotencyKeyHeader = None,
    ) -> V3SendResponse | JSONResponse:
        return await idempotent(
            service,
            principal,
            idempotency_key,
            status.HTTP_201_CREATED,
            lambda: service.send_mms(principal, request, service.clock()),
        )


def account_routes(router: APIRouter, service: DeveloperService, caller: Caller) -> None:
    @router.get("/account", response_model=V3Account)
    async def account(principal: Annotated[Principal, caller]) -> V3Account:
        return await service.account(principal, service.clock())

    @router.get("/account/balance", response_model=V3Balance)
    async def balance(principal: Annotated[Principal, caller]) -> V3Balance:
        return await service.balance(principal, service.clock())


def list_routes(router: APIRouter, service: DeveloperService, caller: Caller) -> None:
    @router.get("/lists", response_model=list[V3List])
    async def lists(principal: Annotated[Principal, caller], q: str | None = None) -> list[V3List]:
        return await service.lists(principal, q)

    @router.post("/lists", response_model=None, status_code=status.HTTP_201_CREATED)
    async def create_list(
        principal: Annotated[Principal, caller],
        request: V3ListRequest,
        idempotency_key: IdempotencyKeyHeader = None,
    ) -> V3List | JSONResponse:
        return await idempotent(
            service,
            principal,
            idempotency_key,
            status.HTTP_201_CREATED,
            lambda: service.create_list(principal, request),
        )


def contact_routes(router: APIRouter, service: DeveloperService, caller: Caller) -> None:
    @router.get("/lists/{listId}/contacts", response_model=V3ContactPage)
    async def contacts(
        principal: Annotated[Principal, caller],
        list_id: Annotated[str, Path(alias="listId")],
        cursor: str | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> V3ContactPage:
        return await service.list_contacts(principal, list_id, cursor, limit)

    @router.post(
        "/lists/{listId}/contacts", response_model=None, status_code=status.HTTP_201_CREATED
    )
    async def add_contact(
        principal: Annotated[Principal, caller],
        list_id: Annotated[str, Path(alias="listId")],
        request: V3ContactInput | V3ContactBatch,
        idempotency_key: IdempotencyKeyHeader = None,
    ) -> V3ContactCreated | V3ContactBatchResult | JSONResponse:
        async def work() -> V3ContactCreated | V3ContactBatchResult:
            if isinstance(request, V3ContactBatch):
                added = await service.add_contacts(principal, list_id, request.contacts)
                return V3ContactBatchResult(contacts=added)
            return await service.add_contact(principal, list_id, request)

        return await idempotent(service, principal, idempotency_key, status.HTTP_201_CREATED, work)

    @router.delete("/lists/{listId}/contacts/{contactId}", status_code=status.HTTP_204_NO_CONTENT)
    async def remove_contact(
        principal: Annotated[Principal, caller],
        list_id: Annotated[str, Path(alias="listId")],
        contact_id: Annotated[str, Path(alias="contactId")],
    ) -> None:
        await service.remove_contact(principal, list_id, contact_id)


def catalogue_routes(router: APIRouter, service: DeveloperService, caller: Caller) -> None:
    @router.get("/sender-ids", response_model=V3SenderIdsResponse)
    async def sender_ids(principal: Annotated[Principal, caller]) -> V3SenderIdsResponse:
        return await service.sender_ids(principal)

    @router.get("/templates", response_model=V3TemplatesResponse)
    async def templates(principal: Annotated[Principal, caller]) -> V3TemplatesResponse:
        return await service.templates(principal)


def general_routes(router: APIRouter, service: DeveloperService, caller: Caller) -> None:
    @router.get("/general", dependencies=[caller], response_model=DeveloperGeneral)
    async def general() -> DeveloperGeneral:
        return await service.general()

    @router.get("/logs", response_model=LogsPage)
    async def logs(
        principal: Annotated[Principal, caller],
        endpoint: str | None = None,
        outcome: str | None = None,
        since: datetime | None = None,
        subaccount: str | None = None,
        until: datetime | None = None,
    ) -> LogsPage:
        filters = LogFilters(outcome=outcome, route=endpoint, user_id=subaccount)
        return await service.logs(principal, filters, since, until, service.clock())


def build_router(service: DeveloperService, authenticated: Authenticated) -> APIRouter:
    router = APIRouter(prefix=APP_PREFIX)
    general_routes(router, service, Depends(authenticated))
    return router

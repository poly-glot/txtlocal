from collections.abc import Awaitable, Callable
from datetime import datetime
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated, Protocol

from fastapi import APIRouter, Depends, Path, Query, Request, Response, params, status
from fastapi.responses import StreamingResponse

from txtlocal.slices.campaigns.model import QuickQuote, QuickSendResult
from txtlocal.slices.messaging.model import (
    HistoryPage,
    HistoryQuery,
    MediaUploadRequest,
    MediaUploadResponse,
    MessageRow,
    QuickSendRequest,
    Template,
    TemplateRequest,
)

if TYPE_CHECKING:
    from txtlocal.slices.identity.model import Principal
    from txtlocal.slices.messaging.service import MessagingService

type Authenticated = Callable[[Request], Awaitable[Principal]]
type Caller = params.Depends

CSV_MEDIA_TYPE = "text/csv"
CSV_RESPONSES: dict[int | str, dict[str, object]] = {
    HTTPStatus.OK: {"content": {CSV_MEDIA_TYPE: {"schema": {"type": "string"}}}}
}
EXPORT_DISPOSITION = 'attachment; filename="sms-history.csv"'


class QuickSend(Protocol):
    async def quote_quick(
        self, principal: Principal, request: QuickSendRequest, now: datetime
    ) -> QuickQuote: ...

    async def send_quick(
        self, principal: Principal, request: QuickSendRequest, now: datetime
    ) -> QuickSendResult: ...


def build_router(
    service: MessagingService, authenticated: Authenticated, quick_send: QuickSend
) -> APIRouter:
    router = APIRouter(prefix="/api/app")
    caller = Depends(authenticated)
    message_routes(router, service, caller, quick_send)
    template_routes(router, service, caller)
    media_routes(router, service)
    return router


def message_routes(
    router: APIRouter, service: MessagingService, caller: Caller, quick_send: QuickSend
) -> None:
    @router.post("/messages/quote", response_model=QuickQuote)
    async def quote(
        principal: Annotated[Principal, caller], request: QuickSendRequest
    ) -> QuickQuote:
        return await quick_send.quote_quick(principal, request, service.clock())

    @router.post("/messages/send", response_model=QuickSendResult)
    async def send(
        principal: Annotated[Principal, caller], request: QuickSendRequest
    ) -> QuickSendResult:
        return await quick_send.send_quick(principal, request, service.clock())

    @router.get("/messages", response_model=HistoryPage)
    async def history(
        principal: Annotated[Principal, caller], query: Annotated[HistoryQuery, Query()]
    ) -> HistoryPage:
        return await service.history(principal.account_id, query, service.clock())

    @router.get("/messages/export", response_class=Response, responses=CSV_RESPONSES)
    async def export(
        principal: Annotated[Principal, caller], query: Annotated[HistoryQuery, Query()]
    ) -> StreamingResponse:
        return StreamingResponse(
            service.export(principal.account_id, query, service.clock()),
            headers={"Content-Disposition": EXPORT_DISPOSITION},
            media_type=CSV_MEDIA_TYPE,
        )

    @router.get("/messages/{messageId}", response_model=MessageRow)
    async def detail(
        principal: Annotated[Principal, caller], message_id: Annotated[str, Path(alias="messageId")]
    ) -> MessageRow:
        return await service.detail(principal.account_id, message_id)


def template_routes(router: APIRouter, service: MessagingService, caller: Caller) -> None:
    @router.get("/templates", response_model=list[Template])
    async def list_templates(principal: Annotated[Principal, caller]) -> list[Template]:
        return await service.list_templates(principal.account_id)

    @router.post("/templates", response_model=Template, status_code=status.HTTP_201_CREATED)
    async def create_template(
        principal: Annotated[Principal, caller], request: TemplateRequest
    ) -> Template:
        return await service.create_template(principal.account_id, request, service.clock())

    @router.put("/templates/{templateId}", response_model=Template)
    async def update_template(
        principal: Annotated[Principal, caller],
        template_id: Annotated[str, Path(alias="templateId")],
        request: TemplateRequest,
    ) -> Template:
        return await service.update_template(principal.account_id, template_id, request)

    @router.delete("/templates/{templateId}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_template(
        principal: Annotated[Principal, caller],
        template_id: Annotated[str, Path(alias="templateId")],
    ) -> None:
        await service.delete_template(principal.account_id, template_id)


def media_routes(router: APIRouter, service: MessagingService) -> None:
    @router.post("/messaging/media", response_model=MediaUploadResponse)
    async def create_media_upload(request: MediaUploadRequest) -> MediaUploadResponse:
        return await service.create_media_upload(request.content_type)

    @router.put("/messaging/media/{key}", status_code=status.HTTP_204_NO_CONTENT)
    async def store_media(key: Annotated[str, Path()], request: Request) -> None:
        await service.store_media(
            key, request.headers.get("content-type", ""), await request.body()
        )

    @router.get("/messaging/media/{key}")
    async def read_media(key: Annotated[str, Path()]) -> Response:
        file = await service.read_media(key)
        return Response(content=file.body, media_type=file.content_type)

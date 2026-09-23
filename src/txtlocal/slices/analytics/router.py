from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, params
from fastapi.responses import RedirectResponse, Response, StreamingResponse

from txtlocal.slices.analytics.model import ReportingPage, ReportingQuery, UsageTabPage
from txtlocal.slices.identity.model import Principal

if TYPE_CHECKING:
    from txtlocal.slices.analytics.service import AnalyticsService

type Authenticated = Callable[[Request], Awaitable[Principal]]
type Caller = params.Depends

CACHE_HEADERS = {"Cache-Control": "public, max-age=300"}
NO_CACHE_HEADERS = {"Cache-Control": "no-store"}
CSV_MEDIA_TYPE = "text/csv"
CSV_RESPONSES: dict[int | str, dict[str, object]] = {
    HTTPStatus.OK: {"content": {CSV_MEDIA_TYPE: {"schema": {"type": "string"}}}}
}
EXPORT_DISPOSITION = 'attachment; filename="usage-reporting.csv"'
MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def build_router(service: AnalyticsService, authenticated: Authenticated) -> APIRouter:
    router = APIRouter(prefix="/api/app/analytics")
    caller = Depends(authenticated)

    @router.get("/usage", response_model=UsageTabPage)
    async def usage(
        principal: Annotated[Principal, caller],
        month: Annotated[str, Query(pattern=MONTH_PATTERN)],
    ) -> UsageTabPage:
        return await service.usage_month(principal.account_id, month)

    @router.get("/reporting", response_model=ReportingPage)
    async def reporting(
        principal: Annotated[Principal, caller], query: Annotated[ReportingQuery, Query()]
    ) -> ReportingPage:
        return await service.reporting(principal.account_id, query)

    @router.get("/reporting/export", response_class=Response, responses=CSV_RESPONSES)
    async def reporting_export(
        principal: Annotated[Principal, caller], query: Annotated[ReportingQuery, Query()]
    ) -> StreamingResponse:
        return StreamingResponse(
            service.reporting_csv(principal.account_id, query),
            headers={"Content-Disposition": EXPORT_DISPOSITION},
            media_type=CSV_MEDIA_TYPE,
        )

    return router


def build_public_router(service: AnalyticsService) -> APIRouter:
    router = APIRouter()

    @router.get("/l/{code}")
    async def redirect(code: Annotated[str, Path()]) -> Response:
        url = await service.resolve_link(code)
        if url is None:
            return Response(headers=NO_CACHE_HEADERS, status_code=404)
        return RedirectResponse(url, headers=CACHE_HEADERS, status_code=302)

    return router

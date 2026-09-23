from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Path, Query, Request, params, status
from fastapi.responses import PlainTextResponse

from txtlocal.slices.campaigns.model import (
    Campaign,
    CampaignDraft,
    CampaignPage,
    CampaignQuery,
    CampaignQuote,
    CampaignReport,
    ScheduleRequest,
)
from txtlocal.slices.campaigns.service import UNSUBSCRIBED_PAGE

if TYPE_CHECKING:
    from txtlocal.slices.campaigns.service import CampaignsService
    from txtlocal.slices.identity.model import Principal

type Authenticated = Callable[[Request], Awaitable[Principal]]
type Caller = params.Depends


def build_router(service: CampaignsService, authenticated: Authenticated) -> APIRouter:
    router = APIRouter(prefix="/api/app/campaigns")
    caller = Depends(authenticated)
    campaign_routes(router, service, caller)
    action_routes(router, service, caller)
    return router


def campaign_routes(router: APIRouter, service: CampaignsService, caller: Caller) -> None:
    @router.get("", response_model=CampaignPage)
    async def list_campaigns(
        principal: Annotated[Principal, caller], query: Annotated[CampaignQuery, Query()]
    ) -> CampaignPage:
        return await service.list(principal.account_id, query)

    @router.post("", response_model=Campaign, status_code=status.HTTP_201_CREATED)
    async def create_campaign(
        principal: Annotated[Principal, caller], draft: CampaignDraft
    ) -> Campaign:
        return await service.create_draft(principal, draft, service.clock())

    @router.get("/{campaignId}", response_model=Campaign)
    async def get_campaign(
        principal: Annotated[Principal, caller],
        campaign_id: Annotated[str, Path(alias="campaignId")],
    ) -> Campaign:
        return await service.get(principal.account_id, campaign_id)

    @router.put("/{campaignId}", response_model=Campaign)
    async def save_campaign(
        principal: Annotated[Principal, caller],
        campaign_id: Annotated[str, Path(alias="campaignId")],
        draft: CampaignDraft,
    ) -> Campaign:
        return await service.save_draft(principal, campaign_id, draft, service.clock())

    @router.delete("/{campaignId}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_campaign(
        principal: Annotated[Principal, caller],
        campaign_id: Annotated[str, Path(alias="campaignId")],
    ) -> None:
        await service.delete_draft(principal, campaign_id)


def action_routes(router: APIRouter, service: CampaignsService, caller: Caller) -> None:
    @router.post("/{campaignId}/quote", response_model=CampaignQuote)
    async def quote_campaign(
        principal: Annotated[Principal, caller],
        campaign_id: Annotated[str, Path(alias="campaignId")],
    ) -> CampaignQuote:
        return await service.quote(principal, campaign_id, service.clock())

    @router.post("/{campaignId}/schedule", response_model=Campaign)
    async def schedule_campaign(
        principal: Annotated[Principal, caller],
        campaign_id: Annotated[str, Path(alias="campaignId")],
        request: ScheduleRequest,
    ) -> Campaign:
        send_at = None if request.now else request.send_at
        return await service.schedule(principal, campaign_id, send_at, service.clock())

    @router.post("/{campaignId}/cancel", response_model=Campaign)
    async def cancel_campaign(
        principal: Annotated[Principal, caller],
        campaign_id: Annotated[str, Path(alias="campaignId")],
    ) -> Campaign:
        return await service.cancel(principal, campaign_id, service.clock())

    @router.post("/{campaignId}/duplicate", response_model=Campaign)
    async def duplicate_campaign(
        principal: Annotated[Principal, caller],
        campaign_id: Annotated[str, Path(alias="campaignId")],
    ) -> Campaign:
        return await service.duplicate(principal, campaign_id, service.clock())

    @router.get("/{campaignId}/report", response_model=CampaignReport)
    async def report_campaign(
        principal: Annotated[Principal, caller],
        campaign_id: Annotated[str, Path(alias="campaignId")],
    ) -> CampaignReport:
        return await service.report(principal, campaign_id)


def build_public_router(service: CampaignsService) -> APIRouter:
    router = APIRouter(prefix="/api/u")

    @router.get("/{token}", response_class=PlainTextResponse)
    async def unsubscribe(token: Annotated[str, Path()]) -> str:
        await service.unsubscribe(token, service.clock())
        return UNSUBSCRIBED_PAGE

    return router

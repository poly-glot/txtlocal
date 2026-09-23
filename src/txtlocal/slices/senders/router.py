from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from txtlocal.slices.identity.model import Principal
from txtlocal.slices.senders.model import (
    AlphaTagRequest,
    NumberCataloguePage,
    NumberSearchQuery,
    OwnNumberRequest,
    SendersView,
    SenderView,
    SmartSender,
    SmartSenderRequest,
    VerificationRequest,
)

if TYPE_CHECKING:
    from txtlocal.slices.senders.service import SendersService

NUMBERS_PREFIX = "/api/app/numbers"
PREFIX = "/api/app/senders"


def build_router(
    service: SendersService, authenticated: Callable[[Request], Awaitable[Principal]]
) -> APIRouter:
    router = APIRouter(prefix=PREFIX)
    caller = Annotated[Principal, Depends(authenticated)]

    @router.get("")
    async def overview(principal: caller) -> SendersView:
        senders = await service.senders(principal.account_id)
        smarts = await service.smart_senders(principal.account_id)
        return SendersView.of(senders, smarts)

    @router.put("/smart/{country}")
    async def set_smart(country: str, body: SmartSenderRequest, principal: caller) -> SmartSender:
        return await service.set_smart(principal.account_id, country, body)

    @router.post("/own", status_code=HTTPStatus.CREATED)
    async def add_own(body: OwnNumberRequest, principal: caller) -> SenderView:
        return SenderView.of(await service.add_own(principal.account_id, body))

    @router.post("/own/{senderId}/verify")
    async def verify_own(
        sender_id: Annotated[str, Path(alias="senderId")],
        body: VerificationRequest,
        principal: caller,
    ) -> SenderView:
        return SenderView.of(await service.verify_own(principal.account_id, sender_id, body))

    @router.post("/alpha", status_code=HTTPStatus.CREATED)
    async def register_alpha(body: AlphaTagRequest, principal: caller) -> SenderView:
        return SenderView.of(await service.register_alpha(principal.account_id, body))

    @router.delete("/{senderId}", status_code=HTTPStatus.NO_CONTENT)
    async def remove(sender_id: Annotated[str, Path(alias="senderId")], principal: caller) -> None:
        await service.remove(principal.account_id, sender_id)

    return router


def build_numbers_router(
    service: SendersService, authenticated: Callable[[Request], Awaitable[Principal]]
) -> APIRouter:
    router = APIRouter(prefix=NUMBERS_PREFIX)
    caller = Annotated[Principal, Depends(authenticated)]

    @router.get("")
    async def catalogue(
        _principal: caller, query: Annotated[NumberSearchQuery, Query()]
    ) -> NumberCataloguePage:
        return await service.search_numbers(query)

    @router.post("/{number}/buy", status_code=HTTPStatus.CREATED)
    async def buy(number: Annotated[str, Path()], principal: caller) -> SenderView:
        return SenderView.of(await service.buy_number(principal.account_id, number))

    return router

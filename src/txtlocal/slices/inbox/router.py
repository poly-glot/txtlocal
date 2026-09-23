import uuid
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Request

from txtlocal.shared.bus import Bus, Topic
from txtlocal.shared.phone import E164
from txtlocal.slices.billing.model import Page
from txtlocal.slices.campaigns.model import QuickSendResult
from txtlocal.slices.identity.model import Principal
from txtlocal.slices.inbox.model import (
    ConversationStatus,
    ConversationView,
    DemoInboundRequest,
    ProviderInboundSms,
    ReplyRequest,
    ThreadPage,
)

if TYPE_CHECKING:
    from txtlocal.slices.inbox.service import InboxService

CONVERSATIONS_PREFIX = "/api/app/conversations"
DEMO_PREFIX = "/api/app/demo"

type Authenticated = Callable[[Request], Awaitable[Principal]]


def build_router(service: InboxService, authenticated: Authenticated) -> APIRouter:
    router = APIRouter(prefix=CONVERSATIONS_PREFIX)
    caller = Annotated[Principal, Depends(authenticated)]

    @router.get("")
    async def list_conversations(
        principal: caller,
        status: ConversationStatus | None = None,
        q: str | None = None,
        cursor: str | None = None,
    ) -> Page[ConversationView]:
        return await service.list_conversations(principal.account_id, status, q, cursor)

    @router.get("/{peer}")
    async def thread(peer: str, principal: caller, cursor: str | None = None) -> ThreadPage:
        return await service.thread(principal.account_id, E164(peer), cursor)

    @router.post("/{peer}/messages", status_code=HTTPStatus.CREATED)
    async def reply(peer: str, body: ReplyRequest, principal: caller) -> QuickSendResult:
        return await service.reply(principal.account_id, E164(peer), body)

    @router.post("/{peer}/read")
    async def mark_read(peer: str, principal: caller) -> ConversationView:
        return await service.mark_read(principal.account_id, E164(peer))

    @router.post("/{peer}/close")
    async def close(peer: str, principal: caller) -> ConversationView:
        return await service.close(principal.account_id, E164(peer))

    @router.post("/{peer}/reopen")
    async def reopen(peer: str, principal: caller) -> ConversationView:
        return await service.reopen(principal.account_id, E164(peer))

    @router.post("/read-all", status_code=HTTPStatus.NO_CONTENT)
    async def read_all(principal: caller) -> None:
        await service.mark_all_read(principal.account_id)

    return router


def build_demo_router(bus: Bus) -> APIRouter:
    router = APIRouter(prefix=DEMO_PREFIX)

    @router.post("/inbound", status_code=HTTPStatus.ACCEPTED)
    async def demo_inbound(body: DemoInboundRequest) -> None:
        provider = ProviderInboundSms(
            destination_number=body.to,
            inbound_message_id=str(uuid.uuid7()),
            message_body=body.body,
            origination_number=body.from_,
            previous_published_message_id=body.previous_message_id,
        )
        await bus.publish(Topic.SMS_INBOUND, provider.model_dump_json(by_alias=True))

    return router

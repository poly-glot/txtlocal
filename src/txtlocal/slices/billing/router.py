from collections.abc import Awaitable, Callable, Coroutine
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated, Any, assert_never

from fastapi import APIRouter, Depends, Request

from txtlocal.shared.clock import utc_now
from txtlocal.shared.errors import Forbidden
from txtlocal.slices.billing.model import (
    BillingSummary,
    CardView,
    CheckoutUrl,
    CreateTopUpRequest,
    GeneralSettings,
    GeneralUpdate,
    LedgerEntry,
    LedgerOrder,
    PackagesView,
    Page,
    TopUpCreated,
    TopUpStatusView,
    UpcomingCharge,
)
from txtlocal.slices.identity.model import Principal, Role

if TYPE_CHECKING:
    from txtlocal.slices.billing.service import BillingService

type Authenticated = Callable[[Request], Awaitable[Principal]]

OWNER_ONLY = "Billing is available to the account owner only"


def owner_of(authenticated: Authenticated) -> Callable[[Principal], Coroutine[Any, Any, Principal]]:
    async def owner(principal: Annotated[Principal, Depends(authenticated)]) -> Principal:
        role = principal.role
        match role:
            case Role.OWNER:
                return principal
            case Role.SUB:
                raise Forbidden(OWNER_ONLY)
            case _:
                assert_never(role)

    return owner


def register_account_routes(
    router: APIRouter, service: BillingService, authenticated: Authenticated
) -> None:
    caller = Annotated[Principal, Depends(owner_of(authenticated))]

    @router.get("/summary", response_model=BillingSummary)
    async def summary(principal: caller) -> BillingSummary:
        return await service.summary(principal.account_id)

    @router.get("/packages")
    async def packages(_principal: caller, country: str = "GB") -> PackagesView:
        return await service.packages(country)

    @router.get("/transactions", response_model=Page[LedgerEntry])
    async def transactions(
        principal: caller, cursor: str | None = None, order: LedgerOrder = LedgerOrder.DESC
    ) -> Page[LedgerEntry]:
        return await service.transactions(principal.account_id, cursor or None, order)


def register_top_up_routes(
    router: APIRouter, service: BillingService, authenticated: Authenticated
) -> None:
    caller = Annotated[Principal, Depends(owner_of(authenticated))]

    @router.post("/top-ups", status_code=HTTPStatus.CREATED)
    async def create_top_up(body: CreateTopUpRequest, principal: caller) -> TopUpCreated:
        return await service.create_top_up(principal.account_id, body, utc_now())

    @router.get("/top-ups/{top_up_id}")
    async def top_up_status(top_up_id: str, principal: caller) -> TopUpStatusView:
        return await service.top_up_status(principal.account_id, top_up_id)


def register_card_routes(
    router: APIRouter, service: BillingService, authenticated: Authenticated
) -> None:
    caller = Annotated[Principal, Depends(owner_of(authenticated))]

    @router.get("/cards")
    async def cards(principal: caller) -> list[CardView]:
        return await service.cards(principal.account_id)

    @router.post("/cards", status_code=HTTPStatus.CREATED)
    async def add_card(principal: caller) -> CheckoutUrl:
        return await service.add_card(principal.account_id)

    @router.put("/cards/{payment_method_id}/default", status_code=HTTPStatus.NO_CONTENT)
    async def set_default_card(payment_method_id: str, principal: caller) -> None:
        await service.set_default_card(principal.account_id, payment_method_id)

    @router.delete("/cards/{payment_method_id}", status_code=HTTPStatus.NO_CONTENT)
    async def remove_card(payment_method_id: str, principal: caller) -> None:
        await service.remove_card(principal.account_id, payment_method_id)


def register_general_routes(
    router: APIRouter, service: BillingService, authenticated: Authenticated
) -> None:
    caller = Annotated[Principal, Depends(owner_of(authenticated))]

    @router.get("/general")
    async def general(principal: caller) -> GeneralSettings:
        return await service.general(principal.account_id)

    @router.put("/general")
    async def update_general(body: GeneralUpdate, principal: caller) -> GeneralSettings:
        return await service.update_general(principal.account_id, body)

    @router.get("/upcoming-charges")
    async def upcoming_charges(principal: caller) -> list[UpcomingCharge]:
        return await service.upcoming_charges(principal.account_id)


def build_router(service: BillingService, authenticated: Authenticated) -> APIRouter:
    router = APIRouter(prefix="/api/app/billing")

    register_account_routes(router, service, authenticated)
    register_top_up_routes(router, service, authenticated)
    register_card_routes(router, service, authenticated)
    register_general_routes(router, service, authenticated)

    return router

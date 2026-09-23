import hmac
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Path, Request, params

from txtlocal.shared.errors import Unauthorized
from txtlocal.slices.automation.model import (
    DeliveryReportRuleCreated,
    DeliveryReportRuleRequest,
    DeliveryReportRuleView,
    DemoInboundEmailRequest,
    EmailSender,
    EmailSenderRequest,
    InboundRule,
    InboundRuleRequest,
    Website,
    WebsiteRejectionRequest,
    WebsitesRequest,
)

if TYPE_CHECKING:
    from txtlocal.slices.automation.service import AutomationService
    from txtlocal.slices.identity.model import Principal

type Authenticated = Callable[[Request], Awaitable[Principal]]
type Caller = params.Depends

DEMO_PREFIX = "/api/app/demo"
OPERATOR_PREFIX = "/api/operator"
OPERATOR_HEADER = "X-Operator-Secret"
OPERATOR_UNAUTHORIZED = "Invalid operator secret"
PREFIX = "/api/app"


def build_router(service: AutomationService, authenticated: Authenticated) -> APIRouter:
    router = APIRouter(prefix=PREFIX)
    caller = Depends(authenticated)

    inbound_rule_routes(router, service, caller)
    delivery_rule_routes(router, service, caller)
    website_routes(router, service, caller)
    email_sender_routes(router, service, caller)
    return router


def inbound_rule_routes(router: APIRouter, service: AutomationService, caller: Caller) -> None:
    @router.get("/rules/inbound", response_model=list[InboundRule])
    async def list_inbound_rules(principal: Annotated[Principal, caller]) -> list[InboundRule]:
        return await service.inbound_rules(principal.account_id)

    @router.post("/rules/inbound", response_model=InboundRule, status_code=HTTPStatus.CREATED)
    async def create_inbound_rule(
        principal: Annotated[Principal, caller], request: InboundRuleRequest
    ) -> InboundRule:
        return await service.create_inbound_rule(principal.account_id, request)

    @router.put("/rules/inbound/{ruleId}", response_model=InboundRule)
    async def update_inbound_rule(
        principal: Annotated[Principal, caller],
        rule_id: Annotated[str, Path(alias="ruleId")],
        request: InboundRuleRequest,
    ) -> InboundRule:
        return await service.update_inbound_rule(principal.account_id, rule_id, request)

    @router.delete("/rules/inbound/{ruleId}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_inbound_rule(
        principal: Annotated[Principal, caller], rule_id: Annotated[str, Path(alias="ruleId")]
    ) -> None:
        await service.delete_inbound_rule(principal.account_id, rule_id)

    @router.post("/webhooks/{ruleId}/test", status_code=HTTPStatus.ACCEPTED)
    async def test_webhook(
        principal: Annotated[Principal, caller], rule_id: Annotated[str, Path(alias="ruleId")]
    ) -> None:
        await service.test_webhook(principal.account_id, rule_id)


def delivery_rule_routes(router: APIRouter, service: AutomationService, caller: Caller) -> None:
    @router.get("/rules/delivery", response_model=list[DeliveryReportRuleView])
    async def list_delivery_rules(
        principal: Annotated[Principal, caller],
    ) -> list[DeliveryReportRuleView]:
        return await service.delivery_rules(principal.account_id)

    @router.post(
        "/rules/delivery", response_model=DeliveryReportRuleCreated, status_code=HTTPStatus.CREATED
    )
    async def create_delivery_rule(
        principal: Annotated[Principal, caller], request: DeliveryReportRuleRequest
    ) -> DeliveryReportRuleCreated:
        return await service.create_delivery_rule(principal.account_id, request)

    @router.put("/rules/delivery/{ruleId}", response_model=DeliveryReportRuleView)
    async def update_delivery_rule(
        principal: Annotated[Principal, caller],
        rule_id: Annotated[str, Path(alias="ruleId")],
        request: DeliveryReportRuleRequest,
    ) -> DeliveryReportRuleView:
        return await service.update_delivery_rule(principal.account_id, rule_id, request)

    @router.delete("/rules/delivery/{ruleId}", status_code=HTTPStatus.NO_CONTENT)
    async def delete_delivery_rule(
        principal: Annotated[Principal, caller], rule_id: Annotated[str, Path(alias="ruleId")]
    ) -> None:
        await service.delete_delivery_rule(principal.account_id, rule_id)


def website_routes(router: APIRouter, service: AutomationService, caller: Caller) -> None:
    @router.get("/websites", response_model=list[Website])
    async def list_websites(principal: Annotated[Principal, caller]) -> list[Website]:
        return await service.websites(principal.account_id)

    @router.post("/websites", response_model=list[Website], status_code=HTTPStatus.CREATED)
    async def register_websites(
        principal: Annotated[Principal, caller], request: WebsitesRequest
    ) -> list[Website]:
        return await service.register_websites(principal.account_id, request)


def email_sender_routes(router: APIRouter, service: AutomationService, caller: Caller) -> None:
    @router.get("/email-senders", response_model=list[EmailSender])
    async def list_email_senders(principal: Annotated[Principal, caller]) -> list[EmailSender]:
        return await service.email_senders(principal.account_id)

    @router.post("/email-senders", response_model=EmailSender, status_code=HTTPStatus.CREATED)
    async def add_email_sender(
        principal: Annotated[Principal, caller], request: EmailSenderRequest
    ) -> EmailSender:
        return await service.add_email_sender(principal.account_id, request)

    @router.delete("/email-senders/{id}", status_code=HTTPStatus.NO_CONTENT)
    async def remove_email_sender(
        principal: Annotated[Principal, caller],
        email_sender_id: Annotated[str, Path(alias="id")],
    ) -> None:
        await service.remove_email_sender(principal.account_id, email_sender_id)


def build_operator_router(service: AutomationService, secret: str) -> APIRouter:
    router = APIRouter(prefix=OPERATOR_PREFIX)

    async def authorized(request: Request) -> None:
        provided = request.headers.get(OPERATOR_HEADER)
        if not secret or provided is None or not hmac.compare_digest(provided, secret):
            raise Unauthorized(OPERATOR_UNAUTHORIZED)

    caller: Caller = Depends(authorized)

    @router.post(
        "/accounts/{accountId}/websites/{domain}/approve",
        dependencies=[caller],
        response_model=Website,
    )
    async def approve_website(
        account_id: Annotated[str, Path(alias="accountId")], domain: str
    ) -> Website:
        return await service.approve_website_now(account_id, domain)

    @router.post(
        "/accounts/{accountId}/websites/{domain}/reject",
        dependencies=[caller],
        response_model=Website,
    )
    async def reject_website(
        account_id: Annotated[str, Path(alias="accountId")],
        domain: str,
        request: WebsiteRejectionRequest,
    ) -> Website:
        return await service.reject_website(account_id, domain, request)

    return router


def build_email_demo_router(service: AutomationService) -> APIRouter:
    router = APIRouter(prefix=DEMO_PREFIX)

    @router.post("/inbound-email", status_code=HTTPStatus.ACCEPTED)
    async def demo_inbound_email(request: DemoInboundEmailRequest) -> None:
        await service.handle_inbound_email(request, service.clock())

    return router

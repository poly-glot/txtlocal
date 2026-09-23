from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Path

from txtlocal.slices.identity.model import (
    AccountSettings,
    CreatedUser,
    CreateUser,
    HomeView,
    IssuedKey,
    MessagingSettings,
    MeView,
    Principal,
    Profile,
    ProfileUpdate,
    SessionRequest,
    TokenUse,
    UserRow,
    UserUpdate,
)

if TYPE_CHECKING:
    from txtlocal.slices.identity.service import Authenticated, IdentityService

PREFIX = "/api/app"
UserId = Annotated[str, Path(alias="userId")]


def build_router(service: IdentityService, authenticated: Authenticated) -> APIRouter:
    router = APIRouter(prefix=PREFIX)
    add_session_routes(router, service, authenticated)
    add_settings_routes(router, service, authenticated)
    add_user_routes(router, service, authenticated)
    return router


def add_session_routes(
    router: APIRouter, service: IdentityService, authenticated: Authenticated
) -> None:
    @router.post("/session")
    async def open_session(body: SessionRequest) -> MeView:
        claims = await service.verifier.verify(body.id_token, TokenUse.ID)
        principal = await service.open_session(claims)
        return await service.me(principal)

    @router.get("/me")
    async def me(principal: Annotated[Principal, Depends(authenticated)]) -> MeView:
        return await service.me(principal)

    @router.get("/home")
    async def home(principal: Annotated[Principal, Depends(authenticated)]) -> HomeView:
        return await service.home(principal)

    @router.patch("/me/profile")
    async def update_profile(
        principal: Annotated[Principal, Depends(authenticated)], update: ProfileUpdate
    ) -> Profile:
        return await service.update_profile(principal, update)


def add_settings_routes(
    router: APIRouter, service: IdentityService, authenticated: Authenticated
) -> None:
    @router.get("/account/settings")
    async def account_settings(
        principal: Annotated[Principal, Depends(authenticated)],
    ) -> AccountSettings:
        return await service.account_settings(principal)

    @router.put("/account/settings")
    async def update_account_settings(
        principal: Annotated[Principal, Depends(authenticated)], settings: AccountSettings
    ) -> AccountSettings:
        return await service.update_account_settings(principal, settings)

    @router.get("/account/settings/messaging")
    async def messaging_settings(
        principal: Annotated[Principal, Depends(authenticated)],
    ) -> MessagingSettings:
        return await service.messaging_settings(principal.account_id)

    @router.put("/account/settings/messaging")
    async def update_messaging_settings(
        principal: Annotated[Principal, Depends(authenticated)], settings: MessagingSettings
    ) -> MessagingSettings:
        return await service.update_messaging_settings(principal, settings)


def add_user_routes(
    router: APIRouter, service: IdentityService, authenticated: Authenticated
) -> None:
    @router.get("/account/users")
    async def users(
        principal: Annotated[Principal, Depends(authenticated)], q: str | None = None
    ) -> list[UserRow]:
        return await service.users(principal, q)

    @router.post("/account/users", status_code=201)
    async def create_user(
        principal: Annotated[Principal, Depends(authenticated)], request: CreateUser
    ) -> CreatedUser:
        return await service.create_user(principal, request)

    @router.patch("/account/users/{userId}")
    async def update_user(
        principal: Annotated[Principal, Depends(authenticated)], user_id: UserId, update: UserUpdate
    ) -> UserRow:
        return await service.update_user(principal, user_id, update)

    @router.post("/account/users/{userId}/api-key")
    async def regenerate_api_key(
        principal: Annotated[Principal, Depends(authenticated)], user_id: UserId
    ) -> IssuedKey:
        return await service.regenerate_api_key(principal, user_id)

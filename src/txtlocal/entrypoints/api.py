from collections.abc import Sequence
from typing import Any

from fastapi import APIRouter, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from mangum import Mangum
from starlette.middleware.base import BaseHTTPMiddleware

from txtlocal.entrypoints import wiring
from txtlocal.shared import telemetry
from txtlocal.shared.errors import (
    AppError,
    BadRequest,
    Internal,
    PaymentRequired,
    RateLimited,
    Unauthorized,
    Upstream,
)
from txtlocal.shared.model import Model
from txtlocal.slices.identity.service import api_request_logger

BASIC_AUTH_SCHEME = "basicAuth"
HEALTH = {"status": "ok"}
SERVER_ERROR = 500
V3_TITLE = "txtlocal API v3"
V3_VERSION = "1.0.0"
V3_WWW_AUTHENTICATE = 'Basic realm="txtlocal"'

V3_FIXED_CODES: dict[type[AppError], str] = {PaymentRequired: "INSUFFICIENT_BALANCE"}
V3_FIXED_MESSAGES: dict[type[AppError], str] = {
    Internal: "Something went wrong on our side",
    RateLimited: "Rate limit of 60 requests per minute reached",
    Unauthorized: "Invalid username or API key",
    Upstream: "A provider is unavailable, try again",
}


class ErrorBody(Model):
    code: str
    message: str


REFUSED_RESPONSES: dict[int | str, dict[str, object]] = {
    "default": {"description": "Refused", "model": ErrorBody}
}


def cause_of(failure: AppError, error: Exception) -> str:
    if failure.status < SERVER_ERROR:
        return ""
    return f"{type(error).__name__}: {error}"


async def refused(_: Request, error: Exception) -> JSONResponse:
    failure = error if isinstance(error, AppError) else Internal()
    level = telemetry.ERROR if failure.status >= SERVER_ERROR else telemetry.WARNING
    telemetry.log(
        "api_refused",
        level=level,
        cause=cause_of(failure, error),
        code=failure.code,
        status=failure.status,
    )

    body = ErrorBody(code=failure.code, message=failure.public_message())
    return JSONResponse(body.model_dump(), status_code=failure.status)


async def refused_v3(_: Request, error: Exception) -> JSONResponse:
    failure = error if isinstance(error, AppError) else Internal()
    level = telemetry.ERROR if failure.status >= SERVER_ERROR else telemetry.WARNING
    telemetry.log(
        "api_refused",
        level=level,
        cause=cause_of(failure, error),
        code=failure.code,
        status=failure.status,
    )

    code = V3_FIXED_CODES.get(type(failure), failure.code.upper())
    message = V3_FIXED_MESSAGES.get(type(failure), failure.public_message())
    headers: dict[str, str] = {}
    if isinstance(failure, Unauthorized):
        headers["WWW-Authenticate"] = V3_WWW_AUTHENTICATE
    if isinstance(failure, RateLimited) and failure.retry_after is not None:
        headers["Retry-After"] = str(failure.retry_after)

    return JSONResponse(
        {"code": code, "message": message}, headers=headers, status_code=failure.status
    )


def first_problem(error: Exception) -> str:
    problems = error.errors() if isinstance(error, RequestValidationError) else []
    if not problems:
        return "Invalid request"
    problem = problems[0]
    field = ".".join(str(part) for part in problem["loc"] if part != "body")
    return f"{field}: {problem['msg']}" if field else str(problem["msg"])


async def invalid(request: Request, error: Exception) -> JSONResponse:
    return await refused(request, BadRequest(first_problem(error)))


async def invalid_v3(request: Request, error: Exception) -> JSONResponse:
    return await refused_v3(request, BadRequest(first_problem(error)))


async def health() -> dict[str, str]:
    return HEALTH


class V3App(FastAPI):
    def openapi(self) -> dict[str, Any]:
        if self.openapi_schema is not None:
            return self.openapi_schema

        schema = get_openapi(routes=self.routes, title=self.title, version=self.version)
        schema["components"]["securitySchemes"] = {
            BASIC_AUTH_SCHEME: {"scheme": "basic", "type": "http"}
        }
        for operations in schema["paths"].values():
            for operation in operations.values():
                operation["security"] = [{BASIC_AUTH_SCHEME: []}]

        self.openapi_schema = schema
        return self.openapi_schema


def create_v3_app(router: APIRouter) -> FastAPI:
    v3 = V3App(docs_url=None, openapi_url=None, redoc_url=None, title=V3_TITLE, version=V3_VERSION)
    v3.add_exception_handler(AppError, refused_v3)
    v3.add_exception_handler(RequestValidationError, invalid_v3)
    v3.add_middleware(BaseHTTPMiddleware, dispatch=api_request_logger())
    v3.include_router(router)
    return v3


def create_app(routers: Sequence[APIRouter], v3: FastAPI) -> FastAPI:
    app = FastAPI(
        docs_url=None,
        openapi_url=None,
        redoc_url=None,
        responses=REFUSED_RESPONSES,
        title="txtlocal",
    )
    app.add_exception_handler(AppError, refused)
    app.add_exception_handler(RequestValidationError, invalid)
    app.add_api_route("/api/health", health, methods=["GET"])

    for router in routers:
        app.include_router(router)

    app.mount("/", v3)
    return app


telemetry.configure()
v3_app = create_v3_app(wiring.v3_router())
app = create_app(wiring.routers(), v3_app)
handler = Mangum(app, lifespan="off")

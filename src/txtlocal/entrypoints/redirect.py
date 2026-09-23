from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from mangum import Mangum

from txtlocal.entrypoints import wiring
from txtlocal.shared import telemetry
from txtlocal.slices.analytics.router import build_public_router

if TYPE_CHECKING:
    from mangum.types import LambdaContext, LambdaEvent

    from txtlocal.slices.analytics.service import AnalyticsService

telemetry.configure()


def app_of(service: AnalyticsService) -> FastAPI:
    built = FastAPI(docs_url=None, openapi_url=None, redoc_url=None, title="txtlocal-redirect")
    built.include_router(build_public_router(service))
    return built


def handler(event: LambdaEvent, context: LambdaContext) -> dict[str, Any]:
    return Mangum(app_of(wiring.analytics()), lifespan="off")(event, context)

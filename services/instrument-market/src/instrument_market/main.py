from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from instrument_market.api.catalog import router as catalog_router
from instrument_market.api.health import get_clickhouse_client
from instrument_market.api.health import router as health_router
from instrument_market.api.ingestion import router as ingestion_router
from instrument_market.config import get_settings
from instrument_market.context import current_trace_id
from instrument_market.db import create_local_schema
from instrument_market.errors import ProblemDetail, ServiceError
from instrument_market.middleware import request_context_middleware
from instrument_market.observability import configure_observability


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    if settings.environment == "local":
        create_local_schema()
    with suppress(Exception):
        # Readiness 会持续暴露 ClickHouse 不可用, 进程保持存活便于恢复。
        get_clickhouse_client().initialize()
    yield
    get_clickhouse_client().close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.service_name, lifespan=lifespan)
    configure_observability(app, settings)
    app.middleware("http")(request_context_middleware)
    app.include_router(health_router)
    app.include_router(catalog_router)
    app.include_router(ingestion_router)

    @app.exception_handler(ServiceError)
    async def service_error_handler(_: Request, error: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=error.to_problem(current_trace_id()).model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, error: RequestValidationError) -> JSONResponse:
        problem = ProblemDetail(
            type="https://errors.quant-trading.local/request.invalid",
            title="Request validation failed",
            status=422,
            detail="Request validation failed",
            code="request.invalid",
            trace_id=current_trace_id(),
            details={"errors": error.errors()},
        )
        return JSONResponse(status_code=problem.status, content=problem.model_dump(mode="json"))

    return app


app = create_app()

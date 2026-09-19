from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from trading.api.health import router as health_router
from trading.config import get_settings
from trading.context import current_trace_id
from trading.errors import ProblemDetail, ServiceError
from trading.middleware import request_context_middleware
from trading.observability import configure_observability


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.service_name)
    configure_observability(app, settings)
    app.middleware("http")(request_context_middleware)
    app.include_router(health_router)

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

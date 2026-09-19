from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from kms_adapter.api import router as secrets_router
from kms_adapter.config import get_settings
from kms_adapter.context import current_trace_id
from kms_adapter.errors import ProblemDetail, ServiceError
from kms_adapter.health import router as health_router
from kms_adapter.middleware import request_context_middleware


def create_app() -> FastAPI:
    app = FastAPI(title=get_settings().service_name)
    app.middleware("http")(request_context_middleware)
    app.include_router(health_router)
    app.include_router(secrets_router)

    @app.exception_handler(ServiceError)
    async def service_error_handler(_: Request, error: ServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code,
            content=error.to_problem(current_trace_id()).model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, error: RequestValidationError) -> JSONResponse:
        safe_errors = [
            {
                "type": item["type"],
                "loc": list(item["loc"]),
                "msg": item["msg"],
            }
            for item in error.errors()
        ]
        problem = ProblemDetail(
            type="https://errors.quant-trading.local/request.invalid",
            title="Request validation failed",
            status=422,
            detail="Request validation failed",
            code="request.invalid",
            trace_id=current_trace_id(),
            details={"errors": safe_errors},
        )
        return JSONResponse(status_code=problem.status, content=problem.model_dump(mode="json"))

    return app


app = create_app()

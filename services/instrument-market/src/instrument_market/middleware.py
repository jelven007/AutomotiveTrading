from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog.contextvars
from fastapi import Request, Response
from fastapi.responses import JSONResponse

from instrument_market.context import bind_request_context
from instrument_market.errors import ServiceError

RequestHandler = Callable[[Request], Awaitable[Response]]
PUBLIC_PATHS = frozenset(
    {
        "/health/live",
        "/health/ready",
        "/docs",
        "/openapi.json",
        "/internal/v1/market/quotes",
    }
)


async def request_context_middleware(request: Request, call_next: RequestHandler) -> Response:
    trace_id = request.headers.get("X-Trace-ID") or str(uuid4())
    tenant_id = request.headers.get("X-Tenant-ID")

    if request.url.path not in PUBLIC_PATHS and not tenant_id:
        error = ServiceError(
            code="tenant.missing",
            message="X-Tenant-ID header is required",
            status_code=400,
        )
        return JSONResponse(
            status_code=error.status_code,
            content=error.to_problem(trace_id).model_dump(mode="json"),
            headers={"X-Trace-ID": trace_id},
        )

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(trace_id=trace_id, tenant_id=tenant_id)
    with bind_request_context(tenant_id, trace_id):
        response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    return response

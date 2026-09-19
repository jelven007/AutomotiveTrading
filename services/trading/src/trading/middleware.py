from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog.contextvars
from fastapi import Request, Response

from trading.context import bind_request_context

RequestHandler = Callable[[Request], Awaitable[Response]]


async def request_context_middleware(request: Request, call_next: RequestHandler) -> Response:
    trace_id = request.headers.get("X-Trace-ID") or str(uuid4())

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    with bind_request_context(None, trace_id):
        response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    return response

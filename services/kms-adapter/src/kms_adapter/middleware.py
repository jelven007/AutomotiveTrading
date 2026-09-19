from collections.abc import Awaitable, Callable
from uuid import uuid4

from fastapi import Request, Response

from kms_adapter.context import bind_trace_id

RequestHandler = Callable[[Request], Awaitable[Response]]


async def request_context_middleware(request: Request, call_next: RequestHandler) -> Response:
    trace_id = request.headers.get("X-Trace-ID") or str(uuid4())
    with bind_trace_id(trace_id):
        response = await call_next(request)
    response.headers["X-Trace-ID"] = trace_id
    return response

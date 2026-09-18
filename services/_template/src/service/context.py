from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_tenant_id: ContextVar[str | None] = ContextVar("tenant_id", default=None)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


def current_tenant_id() -> str | None:
    return _tenant_id.get()


def current_trace_id() -> str | None:
    return _trace_id.get()


@contextmanager
def bind_request_context(tenant_id: str | None, trace_id: str) -> Iterator[None]:
    tenant_token = _tenant_id.set(tenant_id)
    trace_token = _trace_id.set(trace_id)
    try:
        yield
    finally:
        _trace_id.reset(trace_token)
        _tenant_id.reset(tenant_token)

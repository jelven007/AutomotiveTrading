from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

from qt_common.errors import ServiceError

_tenant_id: ContextVar[str | None] = ContextVar("tenant_id", default=None)
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)


class MissingTenantError(ServiceError):
    def __init__(self) -> None:
        super().__init__(
            code="tenant.missing",
            message="Tenant context is required",
            status_code=400,
        )


def require_tenant() -> str:
    tenant_id = _tenant_id.get()
    if tenant_id is None:
        raise MissingTenantError
    return tenant_id


def current_trace_id() -> str | None:
    return _trace_id.get()


@contextmanager
def bind_request_context(tenant_id: str, trace_id: str | None = None) -> Iterator[None]:
    tenant_token = _tenant_id.set(tenant_id)
    trace_token = _trace_id.set(trace_id)
    try:
        yield
    finally:
        _trace_id.reset(trace_token)
        _tenant_id.reset(tenant_token)

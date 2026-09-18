import pytest
from qt_common.tenant import (
    MissingTenantError,
    bind_request_context,
    current_trace_id,
    require_tenant,
)


def test_tenant_context_rejects_missing_tenant() -> None:
    with pytest.raises(MissingTenantError):
        require_tenant()


def test_request_context_is_scoped_and_restored() -> None:
    with bind_request_context("tenant-a", "trace-a"):
        assert require_tenant() == "tenant-a"
        assert current_trace_id() == "trace-a"

        with bind_request_context("tenant-b", "trace-b"):
            assert require_tenant() == "tenant-b"
            assert current_trace_id() == "trace-b"

        assert require_tenant() == "tenant-a"
        assert current_trace_id() == "trace-a"

    assert current_trace_id() is None
    with pytest.raises(MissingTenantError):
        require_tenant()

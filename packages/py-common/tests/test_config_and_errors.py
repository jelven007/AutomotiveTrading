from qt_common.config import ServiceSettings
from qt_common.errors import ServiceError


def test_service_settings_load_prefixed_environment(monkeypatch) -> None:
    monkeypatch.setenv("QT_SERVICE_NAME", "risk")
    monkeypatch.setenv("QT_ENVIRONMENT", "test")

    settings = ServiceSettings()

    assert settings.service_name == "risk"
    assert settings.environment == "test"


def test_service_error_serializes_problem_details() -> None:
    error = ServiceError(
        code="tenant.forbidden",
        message="Tenant access denied",
        status_code=403,
        details={"tenant_id": "tenant-a"},
    )

    assert error.to_problem(trace_id="trace-a").model_dump(exclude_none=True) == {
        "type": "https://errors.quant-trading.local/tenant.forbidden",
        "title": "Tenant access denied",
        "status": 403,
        "detail": "Tenant access denied",
        "code": "tenant.forbidden",
        "trace_id": "trace-a",
        "details": {"tenant_id": "tenant-a"},
    }

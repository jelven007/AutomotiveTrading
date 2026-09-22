import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from fastapi.testclient import TestClient
from trading.api.dependencies import get_binance_runtime_manager
from trading.main import app


@app.get("/probe")
def probe() -> dict[str, str]:
    return {"status": "ok"}


client = TestClient(app)


def test_health_endpoints_do_not_require_tenant() -> None:
    live_response = client.get("/health/live")
    ready_response = client.get("/health/ready")
    service_response = client.get("/api/v1/trading/health")

    assert live_response.status_code == 200
    assert live_response.json() == {"status": "ok"}
    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ready"}
    assert service_response.status_code == 200
    assert service_response.json() == {"status": "ready"}
    assert live_response.headers["X-Trace-ID"]


def test_tenant_header_is_not_used_as_an_authentication_boundary() -> None:
    response = client.get("/probe")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_request_context_preserves_trace_id() -> None:
    response = client.get(
        "/probe",
        headers={"X-Tenant-ID": "tenant-1", "X-Trace-ID": "trace-1"},
    )

    assert response.status_code == 200
    assert response.headers["X-Trace-ID"] == "trace-1"


class PartialRuntime:
    async def read_spot(self) -> object:
        return object()

    async def read_usdm(self) -> object:
        raise RuntimeError("USD-M unavailable")


class RuntimeManager:
    current = PartialRuntime()


def test_binance_health_reports_products_independently() -> None:
    app.dependency_overrides[get_binance_runtime_manager] = RuntimeManager
    try:
        response = client.get("/health/binance")
    finally:
        app.dependency_overrides.pop(get_binance_runtime_manager, None)

    assert response.status_code == 200
    assert response.json() == {
        "api": "ready",
        "spot": "ready",
        "usdm": "unavailable",
    }

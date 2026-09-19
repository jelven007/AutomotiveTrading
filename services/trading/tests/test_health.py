import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"

from fastapi.testclient import TestClient
from trading.main import app


@app.get("/probe")
def probe() -> dict[str, str]:
    return {"status": "ok"}


client = TestClient(app)


def test_health_endpoints_do_not_require_tenant() -> None:
    live_response = client.get("/health/live")
    ready_response = client.get("/health/ready")

    assert live_response.status_code == 200
    assert live_response.json() == {"status": "ok"}
    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ready"}
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

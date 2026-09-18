import os

os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["AUTH_JWT_SECRET"] = "test-signing-secret-that-is-at-least-32-bytes"
os.environ["SECRET_ENCRYPTION_KEY"] = "5J7v-vVVlNNJAapSF9Pn5FYe8sPKYB8A6t4s4R_7C2k="

from fastapi.testclient import TestClient
from model_config.main import app

client = TestClient(app)


def test_health_endpoints_do_not_require_tenant() -> None:
    live_response = client.get("/health/live")
    ready_response = client.get("/health/ready")

    assert live_response.status_code == 200
    assert live_response.json() == {"status": "ok"}
    assert ready_response.status_code == 200
    assert ready_response.json() == {"status": "ready"}
    assert live_response.headers["X-Trace-ID"]


def test_request_context_preserves_trace_id() -> None:
    response = client.get("/health/live", headers={"X-Trace-ID": "trace-1"})

    assert response.headers["X-Trace-ID"] == "trace-1"

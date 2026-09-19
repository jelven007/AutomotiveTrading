from __future__ import annotations

from fastapi.testclient import TestClient
from instrument_market.api import health
from instrument_market.main import app

client = TestClient(app)


def test_liveness_does_not_require_tenant() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert response.headers["X-Trace-ID"]


def test_readiness_reports_mysql_and_clickhouse(monkeypatch) -> None:
    monkeypatch.setattr(health, "database_is_ready", lambda: True)
    monkeypatch.setattr(health, "clickhouse_is_ready", lambda: True)

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "dependencies": {"mysql": True, "clickhouse": True},
    }


def test_data_catalog_requires_tenant_and_discloses_partial_transactions() -> None:
    missing_tenant = client.get("/api/v1/market/data-catalog")
    response = client.get(
        "/api/v1/market/data-catalog",
        headers={"X-Tenant-ID": "tenant-1"},
    )

    assert missing_tenant.status_code == 400
    assert response.status_code == 200
    transaction = next(item for item in response.json()["datasets"] if item["key"] == "transaction")
    assert transaction["completeness"] == "partial_possible"

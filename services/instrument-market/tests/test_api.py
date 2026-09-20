from __future__ import annotations

from fastapi.testclient import TestClient
from instrument_market.api import health, history, quotes
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
    body = response.json()
    assert set(body) == {"provider", "datasets"}
    assert body["provider"] == "mootdx"
    transaction = next(item for item in body["datasets"] if item["key"] == "transaction")
    assert transaction["completeness"] == "partial_possible"


def test_latest_quotes_requires_tenant_and_uses_bounded_limit(monkeypatch) -> None:
    class QuoteService:
        def latest_quotes(self, *, limit):
            return {"scope": ["SSE", "SZSE"], "returned": 0, "limit": limit, "items": []}

    monkeypatch.setattr(quotes, "get_market_view_service", lambda: QuoteService())
    missing_tenant = client.get("/api/v1/market/quotes/latest")
    response = client.get(
        "/api/v1/market/quotes/latest?limit=120",
        headers={"X-Tenant-ID": "tenant-1"},
    )

    assert missing_tenant.status_code == 400
    assert response.status_code == 200
    assert response.json() == {
        "scope": ["SSE", "SZSE"],
        "returned": 0,
        "limit": 120,
        "items": [],
    }


def test_history_routes_require_tenant_and_validate_symbol(monkeypatch) -> None:
    class HistoryService:
        def bars(self, **kwargs):
            return {"kind": "bars", **kwargs}

        def minutes(self, **kwargs):
            return {"kind": "minutes", **kwargs}

        def transactions(self, **kwargs):
            return {"kind": "transactions", **kwargs}

    monkeypatch.setattr(history, "get_history_view_service", lambda: HistoryService())
    headers = {"X-Tenant-ID": "tenant-1"}

    assert client.get("/api/v1/market/bars/SSE/600000").status_code == 400
    bars = client.get("/api/v1/market/bars/SSE/600000?limit=120", headers=headers)
    minutes = client.get(
        "/api/v1/market/minutes/SZSE/000001?trade_date=2026-09-18",
        headers=headers,
    )
    transactions = client.get(
        "/api/v1/market/transactions/SSE/600000?limit=50",
        headers=headers,
    )

    assert bars.status_code == 200
    assert bars.json()["limit"] == 120
    assert minutes.json()["trade_date"] == "2026-09-18"
    assert transactions.json()["limit"] == 50
    assert client.get("/api/v1/market/bars/SSE/not-a-code", headers=headers).status_code == 422
    assert client.get("/api/v1/market/bars/BSE/920002", headers=headers).status_code == 422

from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from risk.api import get_authorization_service
from risk.authorizations import RiskAuthorizationService
from risk.db import Base
from risk.main import create_app
from risk.policy import AccountScope
from risk.security import ServiceIdentity, require_service_identity
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def api_client() -> Iterator[TestClient]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    authorization_service = RiskAuthorizationService(
        session,
        clock=lambda: datetime(2026, 9, 19, 8, 0, tzinfo=UTC),
    )
    app = create_app()
    app.dependency_overrides[require_service_identity] = lambda: ServiceIdentity(name="trading")
    app.dependency_overrides[get_authorization_service] = lambda: authorization_service
    with TestClient(app) as client:
        yield client
    session.close()


def policy_payload() -> dict[str, object]:
    return {
        "allowed_scopes": list(AccountScope),
        "allowed_symbols": ["BTCUSDT"],
        "allowed_sources": ["manual"],
        "max_order_notional": "1000",
        "max_daily_notional": "5000",
        "max_position_notional": "3000",
        "max_futures_leverage": 10,
        "min_margin_level": "1.5",
        "min_liquidation_distance": "0.10",
        "max_adl_quantile": 2,
        "max_snapshot_age_seconds": 5,
    }


def order_payload() -> dict[str, object]:
    return {
        "account_scope": "spot",
        "symbol": "BTCUSDT",
        "side": "buy",
        "order_type": "limit",
        "quantity": "0.01",
        "limit_price": "50000",
        "reduce_only": False,
        "source": "manual",
        "leverage": None,
    }


def snapshot_payload() -> dict[str, object]:
    return {
        "as_of": "2026-09-19T08:00:00Z",
        "mark_price": "50000",
        "available_balance": "1000",
        "daily_traded_notional": "100",
        "current_position_notional": "500",
        "margin_level": "2",
        "liquidation_distance": "0.30",
        "adl_quantile": 1,
        "protection_mode": False,
    }


def test_policy_issue_and_single_use_verification(api_client: TestClient) -> None:
    policy_response = api_client.put(
        "/api/v1/risk/policies/tenant-a",
        json=policy_payload(),
    )
    issued = api_client.post(
        "/api/v1/risk/order-authorizations",
        json={
            "tenant_id": "tenant-a",
            "account_id": "account-a",
            "order": order_payload(),
            "snapshot": snapshot_payload(),
        },
    )
    token = issued.json()["approval_token"]
    verify_request = {
        "tenant_id": "tenant-a",
        "account_id": "account-a",
        "order": order_payload(),
    }
    verified = api_client.post(
        "/api/v1/risk/order-authorizations/verify",
        headers={"X-Risk-Approval": token},
        json=verify_request,
    )
    replayed = api_client.post(
        "/api/v1/risk/order-authorizations/verify",
        headers={"X-Risk-Approval": token},
        json=verify_request,
    )

    assert policy_response.status_code == 200
    assert policy_response.json()["version"] == 1
    assert issued.status_code == 201
    assert issued.json()["approved"] is True
    assert verified.json() == {"approved": True}
    assert replayed.json() == {"approved": False}


def test_service_token_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "SERVICE_TOKEN",
        "risk-service-token-that-is-at-least-32-bytes",
    )
    from risk.config import get_settings

    get_settings.cache_clear()
    try:
        with TestClient(create_app()) as client:
            response = client.get("/api/v1/risk/policies/tenant-a")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 401
    assert response.json()["code"] == "auth.service_token_missing"

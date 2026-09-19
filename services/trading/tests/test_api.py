from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from trading.account_operations import AccountOperationsService
from trading.accounts import AccountPermissionSnapshot, TradingAccountService
from trading.api.dependencies import (
    RuntimeGuard,
    get_account_operations_service,
    get_account_service,
    get_order_service,
    get_runtime_guard,
)
from trading.main import create_app
from trading.models import Base
from trading.orders import OrderExecutionResult, OrderService
from trading.secrets import InMemoryEncryptedSecretBackend
from trading.security import Principal, get_principal


class AllowingPermissionProbe:
    def inspect(self, **_: object) -> AccountPermissionSnapshot:
        return AccountPermissionSnapshot(
            external_account_ref="42",
            can_read=True,
            can_spot_trade=True,
            can_margin_trade=True,
            can_futures_trade=True,
            can_withdraw=False,
        )


class AllowingRiskAuthorizer:
    def authorize(self, **_: object) -> bool:
        return True


class RecordingConnector:
    def __init__(self) -> None:
        self.order_count = 0
        self.cancel_count = 0

    def submit_order(self, **_: object) -> OrderExecutionResult:
        self.order_count += 1
        return OrderExecutionResult(
            broker_order_id="exchange-1",
            status="submitted",
        )

    def cancel_order(self, **_: object) -> OrderExecutionResult:
        self.cancel_count += 1
        return OrderExecutionResult(
            broker_order_id="exchange-1",
            status="cancelled",
        )

    def account_snapshot(self, **_: object) -> dict[str, object]:
        return {"balances": [{"asset": "USDT", "free": "100.00"}]}

    def margin_borrow_repay(self, **_: object) -> str:
        return "margin-transaction-1"

    def set_futures_leverage(self, **values: object) -> dict[str, object]:
        return {"symbol": values["symbol"], "leverage": values["leverage"]}


@pytest.fixture
def api_client() -> Iterator[tuple[TestClient, RecordingConnector]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    secret_backend = InMemoryEncryptedSecretBackend()
    connector = RecordingConnector()
    account_service = TradingAccountService(
        session,
        secret_backend,
        AllowingPermissionProbe(),
    )
    order_service = OrderService(
        session,
        secret_backend,
        connector,
        AllowingRiskAuthorizer(),
    )
    account_operations_service = AccountOperationsService(
        session,
        secret_backend,
        connector,
        AllowingRiskAuthorizer(),
    )
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: Principal(
        user_id="user-a",
        tenant_id="tenant-a",
        roles=("tenant_admin", "trader"),
        mfa_verified_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_account_service] = lambda: account_service
    app.dependency_overrides[get_order_service] = lambda: order_service
    app.dependency_overrides[get_account_operations_service] = lambda: account_operations_service
    app.dependency_overrides[get_runtime_guard] = lambda: RuntimeGuard(
        external_kms_configured=True,
        fixed_egress_ip_configured=True,
        live_trading_enabled=True,
        risk_service_configured=True,
    )
    with TestClient(app) as client:
        yield client, connector
    session.close()


def bind_payload() -> dict[str, object]:
    return {
        "alias": "主帐号",
        "market_group": "binance",
        "provider": "binance",
        "environment": "production",
        "credential_type": "hmac",
        "api_key": "api-key-sensitive",
        "private_key_or_secret": "hmac-secret",
        "enabled_scopes": [
            "spot",
            "cross_margin",
            "isolated_margin",
            "usdm_futures",
        ],
        "isolated_symbols": ["BTCUSDT"],
        "ip_whitelist_confirmed": True,
    }


def test_bind_list_enable_and_submit_order(
    api_client: tuple[TestClient, RecordingConnector],
) -> None:
    client, connector = api_client

    bind_response = client.post("/api/v1/trading/accounts/bind", json=bind_payload())

    assert bind_response.status_code == 201
    body = bind_response.json()
    assert body["status"] == "read_only"
    assert "api-key-sensitive" not in bind_response.text
    assert "hmac-secret" not in bind_response.text

    list_response = client.get("/api/v1/trading/accounts")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [body["id"]]

    enable_response = client.post(f"/api/v1/trading/accounts/{body['id']}/enable-trading")
    assert enable_response.status_code == 200
    assert enable_response.json()["trading_enabled"] is True

    snapshot_response = client.get(
        f"/api/v1/trading/accounts/{body['id']}/balances",
        params={"scope": "usdm_futures"},
    )
    assert snapshot_response.status_code == 200
    assert snapshot_response.json()["data"]["balances"][0]["asset"] == "USDT"

    order_response = client.post(
        "/api/v1/trading/orders",
        headers={
            "Idempotency-Key": "api-order-1",
            "X-Risk-Approval": "risk-approved",
        },
        json={
            "account_id": body["id"],
            "account_scope": "spot",
            "symbol": "BTCUSDT",
            "side": "buy",
            "order_type": "market",
            "quantity": "0.01",
            "reduce_only": False,
            "margin_side_effect": "none",
            "source": "manual",
        },
    )
    repeated_response = client.post(
        "/api/v1/trading/orders",
        headers={
            "Idempotency-Key": "api-order-1",
            "X-Risk-Approval": "risk-approved",
        },
        json={
            "account_id": body["id"],
            "account_scope": "spot",
            "symbol": "BTCUSDT",
            "side": "buy",
            "order_type": "market",
            "quantity": "0.01",
            "reduce_only": False,
            "margin_side_effect": "none",
            "source": "manual",
        },
    )

    assert order_response.status_code == 201
    assert order_response.json()["status"] == "submitted"
    assert repeated_response.json()["id"] == order_response.json()["id"]
    assert connector.order_count == 1

    get_response = client.get(f"/api/v1/trading/orders/{order_response.json()['id']}")
    cancel_response = client.post(
        f"/api/v1/trading/orders/{order_response.json()['id']}/cancel",
        headers={"Idempotency-Key": "api-cancel-1"},
    )
    repeated_cancel = client.post(
        f"/api/v1/trading/orders/{order_response.json()['id']}/cancel",
        headers={"Idempotency-Key": "api-cancel-1"},
    )
    assert get_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"
    assert repeated_cancel.json()["id"] == cancel_response.json()["id"]
    assert connector.cancel_count == 1

    loan_response = client.post(
        f"/api/v1/trading/accounts/{body['id']}/margin-loans",
        headers={
            "Idempotency-Key": "margin-borrow-1",
            "X-Risk-Approval": "risk-approved",
        },
        json={
            "account_scope": "cross_margin",
            "asset": "USDT",
            "amount": "10",
        },
    )
    leverage_response = client.put(
        f"/api/v1/trading/accounts/{body['id']}/futures-settings",
        headers={
            "Idempotency-Key": "leverage-change-1",
            "X-Risk-Approval": "risk-approved",
        },
        json={"symbol": "BTCUSDT", "leverage": 5},
    )
    assert loan_response.status_code == 201
    assert loan_response.json()["status"] == "completed"
    assert leverage_response.status_code == 200
    assert leverage_response.json()["broker_reference"] == "BTCUSDT:5"


def test_order_api_requires_idempotency_and_risk_headers(
    api_client: tuple[TestClient, RecordingConnector],
) -> None:
    client, _ = api_client

    response = client.post("/api/v1/trading/orders", json={})

    assert response.status_code == 422
    assert response.json()["code"] == "request.invalid"


def test_runtime_guard_blocks_binding_without_fixed_egress(
    api_client: tuple[TestClient, RecordingConnector],
) -> None:
    client, _ = api_client
    client.app.dependency_overrides[get_runtime_guard] = lambda: RuntimeGuard(
        external_kms_configured=True,
        fixed_egress_ip_configured=False,
        live_trading_enabled=False,
        risk_service_configured=False,
    )

    response = client.post("/api/v1/trading/accounts/bind", json=bind_payload())

    assert response.status_code == 409
    assert response.json()["code"] == "trading.fixed_egress_required"


def test_invalid_binding_returns_serializable_problem_detail(
    api_client: tuple[TestClient, RecordingConnector],
) -> None:
    client, _ = api_client
    payload = bind_payload()
    payload["ip_whitelist_confirmed"] = False

    response = client.post("/api/v1/trading/accounts/bind", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "request.invalid"
    assert "api-key-sensitive" not in response.text
    assert "hmac-secret" not in response.text


def test_protected_api_rejects_missing_bearer_token() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/v1/trading/accounts")

    assert response.status_code == 401
    assert response.json()["code"] == "auth.missing"


def test_kill_switch_blocks_new_orders(
    api_client: tuple[TestClient, RecordingConnector],
) -> None:
    client, _ = api_client
    account = client.post("/api/v1/trading/accounts/bind", json=bind_payload()).json()
    client.post(f"/api/v1/trading/accounts/{account['id']}/enable-trading")

    switch_response = client.post(
        "/api/v1/trading/kill-switch",
        json={"reason": "manual incident response"},
    )
    order_response = client.post(
        "/api/v1/trading/orders",
        headers={
            "Idempotency-Key": "blocked-order",
            "X-Risk-Approval": "risk-approved",
        },
        json={
            "account_id": account["id"],
            "account_scope": "spot",
            "symbol": "BTCUSDT",
            "side": "buy",
            "order_type": "market",
            "quantity": "0.01",
        },
    )

    assert switch_response.status_code == 201
    assert order_response.status_code == 409
    assert order_response.json()["code"] == "trading.guard_rejected"

    release_response = client.delete(f"/api/v1/trading/kill-switch/{switch_response.json()['id']}")
    resumed_order = client.post(
        "/api/v1/trading/orders",
        headers={
            "Idempotency-Key": "resumed-order",
            "X-Risk-Approval": "risk-approved",
        },
        json={
            "account_id": account["id"],
            "account_scope": "spot",
            "symbol": "BTCUSDT",
            "side": "buy",
            "order_type": "market",
            "quantity": "0.01",
        },
    )
    assert release_response.status_code == 200
    assert release_response.json()["active"] is False
    assert resumed_order.status_code == 201

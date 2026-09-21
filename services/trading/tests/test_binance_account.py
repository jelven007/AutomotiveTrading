from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from trading.api.dependencies import (
    RuntimeGuard,
    get_binance_client,
    get_binance_runtime_manager,
    get_runtime_guard,
    get_secret_backend,
)
from trading.binance.permissions import AccountPermissionSnapshot
from trading.db import get_session
from trading.main import create_app
from trading.models import Base, TradingAccount
from trading.secrets import InMemoryEncryptedSecretBackend
from trading.security import Principal, get_principal


class AllowingPermissionProbe:
    def inspect(self, **_: object) -> AccountPermissionSnapshot:
        return AccountPermissionSnapshot(
            external_account_ref="binance-user-42",
            ip_restricted=True,
            can_read=True,
            can_spot_trade=True,
            can_margin_trade=False,
            can_futures_trade=True,
            can_withdraw=False,
            can_internal_transfer=False,
            can_universal_transfer=False,
        )


@pytest.fixture
def binance_api() -> Iterator[tuple[TestClient, InMemoryEncryptedSecretBackend, Session]]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    secret_backend = InMemoryEncryptedSecretBackend()
    permission_probe = AllowingPermissionProbe()
    app = create_app()
    app.dependency_overrides[get_principal] = lambda: Principal(
        user_id="user-a",
        tenant_id="tenant-a",
        roles=("tenant_admin",),
        mfa_verified_at=datetime.now(UTC),
    )
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_secret_backend] = lambda: secret_backend
    app.dependency_overrides[get_binance_client] = lambda: permission_probe
    app.dependency_overrides[get_binance_runtime_manager] = lambda: None
    app.dependency_overrides[get_runtime_guard] = lambda: RuntimeGuard(
        fixed_egress_ip_configured=True,
    )
    with TestClient(app) as client:
        yield client, secret_backend, session
    session.close()


def replacement_payload(alias: str = "主账号") -> dict[str, object]:
    return {
        "alias": alias,
        "api_key": "api-key-sensitive",
        "api_secret": "api-secret-sensitive",
        "ip_whitelist_confirmed": True,
    }


def test_get_binance_account_returns_stable_missing_problem(
    binance_api: tuple[TestClient, InMemoryEncryptedSecretBackend, Session],
) -> None:
    client, _, _ = binance_api

    response = client.get("/api/v1/trading/binance/account")

    assert response.status_code == 404
    assert response.json()["code"] == "binance.account_missing"


def test_replace_binance_account_overwrites_the_single_slot(
    binance_api: tuple[TestClient, InMemoryEncryptedSecretBackend, Session],
) -> None:
    client, secret_backend, session = binance_api

    first = client.put(
        "/api/v1/trading/binance/account",
        json=replacement_payload("主账号"),
    )
    second = client.put(
        "/api/v1/trading/binance/account",
        json=replacement_payload("备用账号"),
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert session.scalar(select(func.count()).select_from(TradingAccount)) == 1
    assert secret_backend.count == 1
    assert set(second.json()) == {
        "alias",
        "api_key_fingerprint",
        "connection_status",
        "last_verified_at",
    }
    assert second.json()["alias"] == "备用账号"
    assert "api-key-sensitive" not in second.text
    assert "api-secret-sensitive" not in second.text


def test_replace_binance_account_rejects_legacy_fields(
    binance_api: tuple[TestClient, InMemoryEncryptedSecretBackend, Session],
) -> None:
    client, _, _ = binance_api
    payload = replacement_payload()
    payload["credential_type"] = "hmac"

    response = client.put("/api/v1/trading/binance/account", json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "request.invalid"


def test_replace_binance_account_requires_fixed_egress(
    binance_api: tuple[TestClient, InMemoryEncryptedSecretBackend, Session],
) -> None:
    client, _, _ = binance_api
    client.app.dependency_overrides[get_runtime_guard] = lambda: RuntimeGuard(
        fixed_egress_ip_configured=False,
    )

    response = client.put(
        "/api/v1/trading/binance/account",
        json=replacement_payload(),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "trading.fixed_egress_required"


def test_delete_binance_account_removes_metadata_and_secret(
    binance_api: tuple[TestClient, InMemoryEncryptedSecretBackend, Session],
) -> None:
    client, secret_backend, session = binance_api
    assert (
        client.put(
            "/api/v1/trading/binance/account",
            json=replacement_payload(),
        ).status_code
        == 200
    )

    deleted = client.delete("/api/v1/trading/binance/account")
    missing = client.get("/api/v1/trading/binance/account")

    assert deleted.status_code == 204
    assert missing.status_code == 404
    assert session.scalar(select(func.count()).select_from(TradingAccount)) == 0
    assert secret_backend.count == 0


def test_legacy_routes_reject_binance_account_lifecycle(
    binance_api: tuple[TestClient, InMemoryEncryptedSecretBackend, Session],
) -> None:
    client, _, _ = binance_api

    assert client.post("/api/v1/trading/accounts/bind", json={}).status_code == 404
    assert client.post("/api/v1/trading/accounts/legacy/activate").status_code == 404
    assert client.post("/api/v1/trading/accounts/active/deactivate").status_code == 404

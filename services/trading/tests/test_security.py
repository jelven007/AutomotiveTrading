from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.exceptions import InvalidTag
from fastapi.security import HTTPAuthorizationCredentials
from trading.config import Settings
from trading.errors import ServiceError
from trading.secrets import LocalCredentialVault
from trading.security import (
    get_principal,
    require_demo_trading_write,
    require_recent_mfa,
)


def settings(*, demo_trading_enabled: bool = False) -> Settings:
    return Settings(
        auth_issuer="https://identity.quant.test",
        auth_audience="quant-api",
        auth_jwt_secret="test-signing-secret-that-is-at-least-32-bytes",
        demo_trading_enabled=demo_trading_enabled,
    )


def token(mfa_time: datetime | None) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": "https://identity.quant.test",
        "aud": "quant-api",
        "sub": "user-a",
        "tenant_id": "tenant-a",
        "roles": ["trader"],
        "iat": now,
        "exp": now + timedelta(minutes=15),
    }
    if mfa_time is not None:
        claims["mfa_time"] = int(mfa_time.timestamp())
    return jwt.encode(
        claims,
        "test-signing-secret-that-is-at-least-32-bytes",
        algorithm="HS256",
    )


def test_principal_uses_signed_tenant_and_recent_mfa(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("trading.security.get_settings", settings)
    principal = get_principal(
        HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token(datetime.now(UTC)),
        )
    )

    assert principal.tenant_id == "tenant-a"
    require_recent_mfa(principal)


def test_missing_mfa_time_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("trading.security.get_settings", settings)
    principal = get_principal(
        HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token(None),
        )
    )

    with pytest.raises(ServiceError) as captured:
        require_recent_mfa(principal)
    assert captured.value.code == "auth.mfa_required"


def test_demo_write_guard_rejects_disabled_trading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("trading.security.get_settings", settings)
    principal = get_principal(
        HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token(datetime.now(UTC)),
        )
    )

    with pytest.raises(ServiceError) as captured:
        require_demo_trading_write(principal)

    assert captured.value.code == "trading.demo_disabled"


def test_demo_write_guard_accepts_enabled_trading_with_recent_mfa(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "trading.security.get_settings",
        lambda: settings(demo_trading_enabled=True),
    )
    principal = get_principal(
        HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=token(datetime.now(UTC)),
        )
    )

    require_demo_trading_write(principal)


def test_local_credential_vault_round_trips_with_random_nonce() -> None:
    vault = LocalCredentialVault(b"m" * 32)
    first = vault.encrypt("account-a", {"api_key": "secret-a"})
    second = vault.encrypt("account-a", {"api_key": "secret-a"})

    assert first[1] != second[1]
    assert first[0] != second[0]
    assert vault.decrypt("account-a", *first) == {"api_key": "secret-a"}


def test_local_credential_vault_binds_ciphertext_to_account() -> None:
    vault = LocalCredentialVault(b"m" * 32)
    encrypted = vault.encrypt("account-a", {"api_key": "secret-a"})

    with pytest.raises(InvalidTag):
        vault.decrypt("account-b", *encrypted)

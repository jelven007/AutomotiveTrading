from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi.security import HTTPAuthorizationCredentials
from trading.config import Settings
from trading.errors import ServiceError
from trading.security import get_principal, require_recent_mfa


def settings() -> Settings:
    return Settings(
        auth_issuer="https://identity.quant.test",
        auth_audience="quant-api",
        auth_jwt_secret="test-signing-secret-that-is-at-least-32-bytes",
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

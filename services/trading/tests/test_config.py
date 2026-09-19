import pytest
from pydantic import ValidationError
from trading.config import Settings


def test_production_requires_authentication_signing_secret() -> None:
    with pytest.raises(ValidationError, match="authentication signing secret"):
        Settings(
            environment="production",
            auth_jwt_secret=None,
            secret_backend="kms",
            kms_url="https://kms.internal",
        )


def test_production_rejects_local_secret_backend() -> None:
    with pytest.raises(ValidationError, match="external KMS"):
        Settings(
            environment="production",
            auth_jwt_secret="test-signing-secret-that-is-at-least-32-bytes",
            secret_backend="local",
        )


def test_live_trading_requires_risk_service_and_fixed_egress() -> None:
    with pytest.raises(ValidationError, match="risk service"):
        Settings(
            environment="production",
            auth_jwt_secret="test-signing-secret-that-is-at-least-32-bytes",
            secret_backend="kms",
            kms_url="https://kms.internal",
            live_trading_enabled=True,
            fixed_egress_ip_configured=True,
        )

    with pytest.raises(ValidationError, match="fixed egress IP"):
        Settings(
            environment="production",
            auth_jwt_secret="test-signing-secret-that-is-at-least-32-bytes",
            secret_backend="kms",
            kms_url="https://kms.internal",
            live_trading_enabled=True,
            risk_service_url="https://risk.internal",
        )

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
            kms_service_token="kms-service-token-that-is-at-least-32-bytes",
            risk_service_token="risk-service-token-that-is-at-least-32-bytes",
            live_trading_enabled=True,
            fixed_egress_ip_configured=True,
        )

    with pytest.raises(ValidationError, match="fixed egress IP"):
        Settings(
            environment="production",
            auth_jwt_secret="test-signing-secret-that-is-at-least-32-bytes",
            secret_backend="kms",
            kms_url="https://kms.internal",
            kms_service_token="kms-service-token-that-is-at-least-32-bytes",
            live_trading_enabled=True,
            risk_service_url="https://risk.internal",
            risk_service_token="risk-service-token-that-is-at-least-32-bytes",
        )


def test_production_requires_independent_kms_and_risk_tokens() -> None:
    with pytest.raises(ValidationError, match="KMS service token"):
        Settings(
            environment="production",
            auth_jwt_secret="test-signing-secret-that-is-at-least-32-bytes",
            secret_backend="kms",
            kms_url="https://kms.internal",
        )

    with pytest.raises(ValidationError, match="risk service token"):
        Settings(
            environment="production",
            auth_jwt_secret="test-signing-secret-that-is-at-least-32-bytes",
            secret_backend="kms",
            kms_url="https://kms.internal",
            kms_service_token="kms-service-token-that-is-at-least-32-bytes",
        )


@pytest.mark.parametrize("field", ["kms_service_token", "risk_service_token"])
def test_production_rejects_short_internal_service_tokens(field: str) -> None:
    values = {
        "environment": "production",
        "auth_jwt_secret": "test-signing-secret-that-is-at-least-32-bytes",
        "secret_backend": "kms",
        "kms_url": "https://kms.internal",
        "kms_service_token": "kms-service-token-that-is-at-least-32-bytes",
        "risk_service_token": "risk-service-token-that-is-at-least-32-bytes",
    }
    values[field] = "too-short"

    with pytest.raises(ValidationError, match="at least 32"):
        Settings(**values)


def test_production_rejects_insecure_internal_http() -> None:
    with pytest.raises(ValidationError, match="internal HTTPS"):
        Settings(
            environment="production",
            auth_jwt_secret="test-signing-secret-that-is-at-least-32-bytes",
            secret_backend="kms",
            kms_url="https://kms.internal",
            kms_service_token="kms-service-token-that-is-at-least-32-bytes",
            risk_service_token="risk-service-token-that-is-at-least-32-bytes",
            allow_insecure_internal_http=True,
        )

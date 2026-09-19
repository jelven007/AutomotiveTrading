import pytest
from kms_adapter.config import Settings
from pydantic import ValidationError


def test_production_requires_service_token_and_kms_key() -> None:
    with pytest.raises(ValidationError, match="service token"):
        Settings(environment="production", kms_key_id="volc-key-id")

    with pytest.raises(ValidationError, match="KMS key ID"):
        Settings(
            environment="production",
            service_token="kms-service-token-that-is-at-least-32-bytes",
        )


def test_production_rejects_short_service_token() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        Settings(
            environment="production",
            service_token="too-short",
            kms_key_id="volc-key-id",
        )


def test_partial_static_credentials_are_rejected() -> None:
    with pytest.raises(ValidationError, match="configured together"):
        Settings(volcengine_access_key="access-key")

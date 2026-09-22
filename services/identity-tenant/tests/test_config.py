import pytest
from identity_tenant.config import Settings
from pydantic import ValidationError


def settings(**overrides: object) -> Settings:
    return Settings(
        auth_jwt_secret="test-signing-secret-that-is-at-least-32-bytes",
        auth_totp_encryption_key="5J7v-vVVlNNJAapSF9Pn5FYe8sPKYB8A6t4s4R_7C2k=",
        **overrides,
    )


def test_production_requires_single_owner_registration_mode() -> None:
    with pytest.raises(ValidationError, match="single-owner"):
        settings(environment="production")

    configured = settings(environment="production", single_owner_mode=True)

    assert configured.single_owner_mode is True

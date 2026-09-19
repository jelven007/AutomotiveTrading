import pytest
from pydantic import ValidationError
from risk.config import Settings


def test_production_requires_strong_service_token() -> None:
    with pytest.raises(ValidationError, match="requires a service token"):
        Settings(environment="production")

    with pytest.raises(ValidationError, match="at least 32"):
        Settings(environment="production", service_token="too-short")

    settings = Settings(
        environment="production",
        service_token="risk-service-token-that-is-at-least-32-bytes",
    )
    assert settings.service_token is not None

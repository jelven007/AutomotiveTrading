from __future__ import annotations

import pytest
from instrument_market.config import Settings
from pydantic import ValidationError


def test_settings_mask_tushare_token_in_repr() -> None:
    settings = Settings(tushare_token="secret-token")

    assert settings.tushare_token.get_secret_value() == "secret-token"
    assert "secret-token" not in repr(settings)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quote_shard_count", 0),
        ("quote_sweep_seconds", 0),
        ("quote_stale_after_seconds", 0),
    ],
)
def test_settings_reject_non_positive_collection_limits(
    field: str,
    value: int,
) -> None:
    with pytest.raises(ValidationError):
        Settings(**{field: value})


def test_settings_use_private_dependency_endpoints_by_default() -> None:
    settings = Settings()

    assert settings.clickhouse_url == "http://clickhouse:8123"
    assert settings.redis_url == "redis://redis:6379/0"
    assert settings.kafka_bootstrap_servers == "kafka:29092"
    assert settings.minio_endpoint == "http://minio:9000"

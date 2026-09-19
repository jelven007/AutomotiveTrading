from functools import lru_cache

from pydantic import Field, PositiveFloat, PositiveInt, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "instrument-market"
    environment: str = "local"
    log_level: str = "INFO"

    database_url: str = "sqlite+pysqlite:///./instrument-market.db"
    clickhouse_url: str = "http://clickhouse:8123"
    clickhouse_database: str = Field(
        default="qt_market",
        pattern=r"^[A-Za-z_][A-Za-z0-9_]*$",
    )
    clickhouse_user: str = "qt_market"
    clickhouse_password: SecretStr = SecretStr("")
    redis_url: str = "redis://redis:6379/0"
    kafka_bootstrap_servers: str = "kafka:29092"
    minio_endpoint: str = "http://minio:9000"
    minio_access_key: SecretStr = SecretStr("")
    minio_secret_key: SecretStr = SecretStr("")
    minio_bucket: str = "market-raw"

    tushare_token: SecretStr = SecretStr("")
    mootdx_collector_url: str = "http://mootdx-collector:8010"
    mootdx_collector_token: SecretStr = SecretStr("")
    ingest_service_token: SecretStr = SecretStr("")
    mootdx_source_id: str = "tdx-auto"
    tdx_data_path: str | None = None
    wal_path: str = "./data/wal"

    quote_shard_count: PositiveInt = 8
    quote_sweep_seconds: PositiveFloat = 2.0
    quote_stale_after_seconds: PositiveFloat = 3.0
    provider_timeout_seconds: PositiveFloat = 10.0
    clickhouse_timeout_seconds: PositiveFloat = 3.0
    max_query_rows: PositiveInt = Field(default=10_000, le=100_000)


@lru_cache
def get_settings() -> Settings:
    return Settings()

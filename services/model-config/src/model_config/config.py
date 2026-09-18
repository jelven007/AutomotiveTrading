from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(default="model-config")
    environment: str = Field(default="local")
    database_url: str = Field(default="sqlite+pysqlite:///./service.db")
    log_level: str = Field(default="INFO")
    auth_issuer: str = Field(default="https://identity.quant-trading.local")
    auth_audience: str = Field(default="quant-api")
    auth_jwt_secret: SecretStr = Field(min_length=32)
    secret_encryption_key: SecretStr


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

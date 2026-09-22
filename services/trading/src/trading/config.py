from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(default="trading")
    environment: str = Field(default="local")
    database_url: str = Field(default="sqlite+pysqlite:///./trading.db")
    log_level: str = Field(default="INFO")
    auth_issuer: str = Field(default="https://identity.quant-trading.local")
    auth_audience: str = Field(default="quant-api")
    auth_jwt_secret: SecretStr | None = None
    mfa_max_age_seconds: int = Field(default=300, ge=60, le=900)
    binance_credential_master_key_file: str = "/opt/quant-trading/secrets/credential-master-key"
    binance_environment: Literal["demo"] = "demo"
    demo_trading_enabled: bool = False

    @model_validator(mode="after")
    def validate_production_dependencies(self) -> "Settings":
        if self.environment == "production" and self.auth_jwt_secret is None:
            raise ValueError("production requires an authentication signing secret")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

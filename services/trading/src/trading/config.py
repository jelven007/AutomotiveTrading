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
    secret_backend: Literal["local", "kms"] = "local"
    local_secret_encryption_key: SecretStr | None = None
    kms_url: str | None = None
    kms_access_token: SecretStr | None = None
    risk_service_url: str | None = None
    live_trading_enabled: bool = False
    fixed_egress_ip_configured: bool = False
    binance_spot_base_url: str = "https://api.binance.com"
    binance_futures_base_url: str = "https://fapi.binance.com"

    @model_validator(mode="after")
    def validate_production_dependencies(self) -> "Settings":
        if self.environment != "production":
            return self
        if self.secret_backend != "kms" or not self.kms_url:
            raise ValueError("production requires an external KMS backend")
        if not self.kms_url.startswith("https://"):
            raise ValueError("production KMS URL must use HTTPS")
        if self.live_trading_enabled and not self.risk_service_url:
            raise ValueError("live trading requires a risk service")
        if self.live_trading_enabled and not self.fixed_egress_ip_configured:
            raise ValueError("live trading requires a fixed egress IP")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

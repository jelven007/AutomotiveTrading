from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SecretBackendType(StrEnum):
    LOCAL = "local"
    KMS = "kms"


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
    secret_backend: SecretBackendType = SecretBackendType.LOCAL
    local_secret_encryption_key: SecretStr | None = None
    kms_url: str | None = None
    kms_service_token: SecretStr | None = None
    risk_service_url: str | None = None
    risk_service_token: SecretStr | None = None
    allow_insecure_internal_http: bool = False
    live_trading_enabled: bool = False
    fixed_egress_ip_configured: bool = False
    max_futures_leverage: int = Field(default=20, ge=1, le=125)
    binance_spot_base_url: str = "https://api.binance.com"
    binance_futures_base_url: str = "https://fapi.binance.com"

    @model_validator(mode="after")
    def validate_production_dependencies(self) -> "Settings":
        if self.environment != "production":
            return self
        if self.allow_insecure_internal_http:
            raise ValueError("production requires internal HTTPS")
        if self.auth_jwt_secret is None:
            raise ValueError("production requires an authentication signing secret")
        if self.secret_backend is not SecretBackendType.KMS or not self.kms_url:
            raise ValueError("production requires an external KMS backend")
        if not self.kms_url.startswith("https://"):
            raise ValueError("production KMS URL must use HTTPS")
        if self.kms_service_token is None:
            raise ValueError("production requires a KMS service token")
        if len(self.kms_service_token.get_secret_value()) < 32:
            raise ValueError("production KMS service token must contain at least 32 characters")
        if self.risk_service_token is None:
            raise ValueError("production requires a risk service token")
        if len(self.risk_service_token.get_secret_value()) < 32:
            raise ValueError("production risk service token must contain at least 32 characters")
        if self.live_trading_enabled and not self.risk_service_url:
            raise ValueError("live trading requires a risk service")
        if self.risk_service_url and not self.risk_service_url.startswith("https://"):
            raise ValueError("production risk service URL must use HTTPS")
        if self.live_trading_enabled and not self.fixed_egress_ip_configured:
            raise ValueError("live trading requires a fixed egress IP")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

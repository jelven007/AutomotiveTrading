from functools import lru_cache

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
    live_trading_enabled: bool = False
    fixed_egress_ip_configured: bool = False
    binance_spot_base_url: str = "https://api.binance.com"
    binance_testnet_enabled: bool = False

    @model_validator(mode="after")
    def validate_production_dependencies(self) -> "Settings":
        if self.environment != "production":
            return self
        if self.auth_jwt_secret is None:
            raise ValueError("production requires an authentication signing secret")
        if self.live_trading_enabled and not self.fixed_egress_ip_configured:
            raise ValueError("live trading requires a fixed egress IP")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

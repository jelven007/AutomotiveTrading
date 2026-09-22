from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from identity_tenant.auth import AuthSettings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(default="identity-tenant")
    environment: str = Field(default="local")
    database_url: str = Field(default="sqlite+pysqlite:///./service.db")
    log_level: str = Field(default="INFO")
    auth_issuer: str = Field(default="https://identity.quant-trading.local")
    auth_audience: str = Field(default="quant-api")
    auth_jwt_secret: SecretStr = Field(min_length=32)
    auth_totp_encryption_key: SecretStr
    access_token_ttl_seconds: int = Field(default=900)
    refresh_token_ttl_seconds: int = Field(default=2_592_000)
    single_owner_mode: bool = False

    @model_validator(mode="after")
    def validate_production_registration(self) -> "Settings":
        if self.environment == "production" and not self.single_owner_mode:
            raise ValueError("production requires single-owner registration mode")
        return self

    def auth_settings(self) -> AuthSettings:
        return AuthSettings(
            issuer=self.auth_issuer,
            audience=self.auth_audience,
            jwt_secret=self.auth_jwt_secret,
            totp_encryption_key=self.auth_totp_encryption_key,
            access_token_ttl_seconds=self.access_token_ttl_seconds,
            refresh_token_ttl_seconds=self.refresh_token_ttl_seconds,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

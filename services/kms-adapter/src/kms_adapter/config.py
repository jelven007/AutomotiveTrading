from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(default="kms-adapter")
    environment: str = Field(default="local")
    database_url: str = Field(default="sqlite+pysqlite:///./kms-adapter.db")
    log_level: str = Field(default="INFO")
    service_token: SecretStr | None = None
    kms_key_id: str | None = None
    kms_region: str = Field(default="cn-beijing")
    secret_purpose: str = Field(default="binance-credentials")
    volcengine_access_key: SecretStr | None = None
    volcengine_secret_key: SecretStr | None = None
    volcengine_session_token: SecretStr | None = None

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if (self.volcengine_access_key is None) != (self.volcengine_secret_key is None):
            raise ValueError("Volcengine access key and secret key must be configured together")
        if self.environment != "production":
            return self
        if self.service_token is None:
            raise ValueError("production requires a service token")
        if len(self.service_token.get_secret_value()) < 32:
            raise ValueError("production service token must contain at least 32 characters")
        if not self.kms_key_id:
            raise ValueError("production requires a KMS key ID")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

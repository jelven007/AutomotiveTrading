from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = Field(default="risk")
    environment: str = Field(default="local")
    database_url: str = Field(default="sqlite+pysqlite:///./risk.db")
    log_level: str = Field(default="INFO")
    service_token: SecretStr | None = None
    approval_ttl_seconds: int = Field(default=60, ge=10, le=300)

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.environment == "production" and self.service_token is None:
            raise ValueError("production requires a service token")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class ProviderType(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    DEEPSEEK = "deepseek"
    OPENAI_COMPATIBLE = "openai_compatible"
    OLLAMA = "ollama"
    VLLM = "vllm"


class Base(DeclarativeBase):
    pass


class ModelConfiguration(Base):
    __tablename__ = "model_configurations"
    __table_args__ = (UniqueConstraint("tenant_id", "name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    provider_type: Mapped[ProviderType] = mapped_column(
        Enum(
            ProviderType,
            native_enum=False,
            values_callable=lambda providers: [provider.value for provider in providers],
        )
    )
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    model_id: Mapped[str] = mapped_column(String(160), nullable=False)
    secret_ref: Mapped[str] = mapped_column(String(160), nullable=False)
    timeout_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False)
    max_concurrency: Mapped[int] = mapped_column(Integer, nullable=False)
    temperature: Mapped[str] = mapped_column(String(16), nullable=False)
    top_p: Mapped[str] = mapped_column(String(16), nullable=False)
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    rpm_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_token_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_cost_limit: Mapped[str] = mapped_column(String(32), nullable=False)
    allowed_environments_json: Mapped[str] = mapped_column(Text, nullable=False)
    availability: Mapped[str] = mapped_column(String(32), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    health_status: Mapped[str] = mapped_column(String(32), default="untested")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)


class StrategyModelReference(Base):
    __tablename__ = "strategy_model_references"
    __table_args__ = (UniqueConstraint("tenant_id", "configuration_id", "strategy_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    configuration_id: Mapped[str] = mapped_column(
        ForeignKey("model_configurations.id"),
        nullable=False,
        index=True,
    )
    strategy_id: Mapped[str] = mapped_column(String(36), nullable=False)

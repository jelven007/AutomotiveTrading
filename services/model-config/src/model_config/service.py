import json
from collections.abc import Callable
from decimal import Decimal
from enum import StrEnum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from model_config.models import ModelConfiguration, ProviderType, StrategyModelReference
from model_config.secrets import SecretBackend
from model_config.validators import (
    Resolver,
    system_resolver,
    validate_base_url_syntax,
    validate_connection_target,
)

PLANNED_PROVIDERS = frozenset({ProviderType.OLLAMA, ProviderType.VLLM})


class SecretStatus(StrEnum):
    CONFIGURED = "configured"


class ConfigurationInUseError(RuntimeError):
    pass


class ConfigurationNotFoundError(LookupError):
    pass


class PlannedProviderError(RuntimeError):
    pass


class AuditPublisher(Protocol):
    def publish(self, event_type: str, payload: dict[str, Any]) -> None: ...


class InMemoryAuditPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    def publish(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append((event_type, payload))


class ConfigurationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    provider_type: ProviderType
    base_url: str
    model_id: str = Field(min_length=1, max_length=160)
    api_key: SecretStr = Field(min_length=1)
    timeout_ms: int = Field(default=30_000, ge=1_000, le=120_000)
    max_retries: int = Field(default=1, ge=0, le=3)
    max_concurrency: int = Field(default=10, ge=1, le=100)
    temperature: Decimal = Field(default=Decimal("0.1"), ge=0, le=2)
    top_p: Decimal = Field(default=Decimal("1"), gt=0, le=1)
    max_output_tokens: int = Field(default=1200, ge=1, le=100_000)
    rpm_limit: int = Field(default=60, ge=1)
    daily_token_limit: int = Field(default=1_000_000, ge=1)
    daily_cost_limit: Decimal = Field(default=Decimal("500.00"), ge=0)
    allowed_environments: list[str] = Field(min_length=1)
    enabled: bool = False


class ConfigurationView(BaseModel):
    id: str
    tenant_id: str
    name: str
    provider_type: ProviderType
    base_url: str
    model_id: str
    secret_ref: str
    secret_status: SecretStatus
    availability: str
    enabled: bool
    health_status: str


class ModelConfigurationService:
    def __init__(
        self,
        session: Session,
        secret_backend: SecretBackend,
        audit_publisher: AuditPublisher | None = None,
        resolver: Resolver = system_resolver,
    ) -> None:
        self.session = session
        self.secret_backend = secret_backend
        self.audit_publisher = audit_publisher or InMemoryAuditPublisher()
        self.resolver = resolver

    def create(
        self,
        *,
        tenant_id: str,
        actor_roles: tuple[str, ...],
        command: ConfigurationCreate,
    ) -> ConfigurationView:
        self._require_tenant_admin(actor_roles)
        validate_base_url_syntax(command.base_url)
        availability = "planned" if command.provider_type in PLANNED_PROVIDERS else "available"
        enabled = command.enabled and availability == "available"
        secret_ref = self.secret_backend.put(tenant_id, command.api_key.get_secret_value())
        record = ModelConfiguration(
            tenant_id=tenant_id,
            name=command.name,
            provider_type=command.provider_type,
            base_url=command.base_url,
            model_id=command.model_id,
            secret_ref=secret_ref,
            timeout_ms=command.timeout_ms,
            max_retries=command.max_retries,
            max_concurrency=command.max_concurrency,
            temperature=str(command.temperature),
            top_p=str(command.top_p),
            max_output_tokens=command.max_output_tokens,
            rpm_limit=command.rpm_limit,
            daily_token_limit=command.daily_token_limit,
            daily_cost_limit=str(command.daily_cost_limit),
            allowed_environments_json=json.dumps(command.allowed_environments),
            availability=availability,
            enabled=enabled,
            health_status="untested",
        )
        self.session.add(record)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            self.secret_backend.delete(secret_ref)
            raise
        self.audit_publisher.publish(
            "model_configuration.created",
            self._audit_payload(record),
        )
        return self._view(record)

    def test_connection(
        self,
        *,
        tenant_id: str,
        actor_roles: tuple[str, ...],
        configuration_id: str,
        connector: Callable[[str, str], bool],
    ) -> bool:
        self._require_tenant_admin(actor_roles)
        record = self._get(tenant_id, configuration_id)
        if record.provider_type in PLANNED_PROVIDERS:
            raise PlannedProviderError("provider is planned and cannot be connected")

        validate_connection_target(record.base_url, resolver=self.resolver, recheck=False)
        result = connector(record.base_url, self.secret_backend.get(record.secret_ref))
        validate_connection_target(record.base_url, resolver=self.resolver, recheck=False)
        record.health_status = "healthy" if result else "unhealthy"
        self.session.commit()
        self.audit_publisher.publish(
            "model_configuration.connection_tested",
            {**self._audit_payload(record), "result": record.health_status},
        )
        return result

    def list_for_tenant(self, tenant_id: str) -> list[ConfigurationView]:
        records = self.session.scalars(
            select(ModelConfiguration)
            .where(ModelConfiguration.tenant_id == tenant_id)
            .order_by(ModelConfiguration.name)
        )
        return [self._view(record) for record in records]

    def delete(
        self,
        *,
        tenant_id: str,
        actor_roles: tuple[str, ...],
        configuration_id: str,
    ) -> None:
        self._require_tenant_admin(actor_roles)
        record = self._get(tenant_id, configuration_id)
        reference_count = self.session.scalar(
            select(func.count())
            .select_from(StrategyModelReference)
            .where(
                StrategyModelReference.tenant_id == tenant_id,
                StrategyModelReference.configuration_id == configuration_id,
            )
        )
        if reference_count:
            raise ConfigurationInUseError("configuration is referenced by a strategy")

        secret_ref = record.secret_ref
        audit_payload = self._audit_payload(record)
        self.session.delete(record)
        self.session.commit()
        self.secret_backend.delete(secret_ref)
        self.audit_publisher.publish("model_configuration.deleted", audit_payload)

    def _get(self, tenant_id: str, configuration_id: str) -> ModelConfiguration:
        record = self.session.scalar(
            select(ModelConfiguration).where(
                ModelConfiguration.id == configuration_id,
                ModelConfiguration.tenant_id == tenant_id,
            )
        )
        if record is None:
            raise ConfigurationNotFoundError("model configuration not found")
        return record

    @staticmethod
    def _require_tenant_admin(actor_roles: tuple[str, ...]) -> None:
        if "tenant_admin" not in actor_roles:
            raise PermissionError("tenant administrator role is required")

    @staticmethod
    def _view(record: ModelConfiguration) -> ConfigurationView:
        return ConfigurationView(
            id=record.id,
            tenant_id=record.tenant_id,
            name=record.name,
            provider_type=record.provider_type,
            base_url=record.base_url,
            model_id=record.model_id,
            secret_ref=record.secret_ref,
            secret_status=SecretStatus.CONFIGURED,
            availability=record.availability,
            enabled=record.enabled,
            health_status=record.health_status,
        )

    @staticmethod
    def _audit_payload(record: ModelConfiguration) -> dict[str, Any]:
        return {
            "tenant_id": record.tenant_id,
            "resource_type": "model_configuration",
            "resource_id": record.id,
            "provider_type": record.provider_type.value,
            "availability": record.availability,
            "enabled": record.enabled,
        }

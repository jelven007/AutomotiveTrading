import json

import pytest
from model_config.models import ModelConfiguration, ProviderType, StrategyModelReference
from model_config.secrets import LocalEncryptedSecretBackend
from model_config.service import (
    ConfigurationCreate,
    ConfigurationInUseError,
    ModelConfigurationService,
    PlannedProviderError,
)
from sqlalchemy import select
from sqlalchemy.orm import Session


def configuration(provider: ProviderType = ProviderType.OPENAI) -> ConfigurationCreate:
    return ConfigurationCreate(
        name="Primary model",
        provider_type=provider,
        base_url="https://api.openai.com/v1",
        model_id="gpt-production",
        api_key="sk-sensitive-value",
        timeout_ms=30_000,
        max_retries=1,
        max_concurrency=10,
        temperature=0.1,
        top_p=1,
        max_output_tokens=1200,
        rpm_limit=60,
        daily_token_limit=1_000_000,
        daily_cost_limit="500.00",
        allowed_environments=["backtest", "simulation"],
        enabled=False,
    )


def test_only_tenant_admin_can_create_configuration(
    config_service: ModelConfigurationService,
) -> None:
    with pytest.raises(PermissionError):
        config_service.create(
            tenant_id="tenant-a",
            actor_roles=("researcher",),
            command=configuration(),
        )


def test_api_key_is_externalized_and_never_returned(
    config_service: ModelConfigurationService,
    secret_backend: LocalEncryptedSecretBackend,
    session: Session,
) -> None:
    result = config_service.create(
        tenant_id="tenant-a",
        actor_roles=("tenant_admin",),
        command=configuration(),
    )

    stored = session.scalar(select(ModelConfiguration))
    assert stored is not None
    assert stored.secret_ref == result.secret_ref
    assert "sk-sensitive-value" not in json.dumps(result.model_dump())
    assert "sk-sensitive-value" not in repr(stored)
    assert secret_backend.get(stored.secret_ref) == "sk-sensitive-value"


@pytest.mark.parametrize("provider", [ProviderType.OLLAMA, ProviderType.VLLM])
def test_local_provider_is_planned_and_cannot_be_tested(
    provider: ProviderType,
    config_service: ModelConfigurationService,
) -> None:
    result = config_service.create(
        tenant_id="tenant-a",
        actor_roles=("tenant_admin",),
        command=configuration(provider),
    )

    assert result.availability == "planned"
    assert result.enabled is False
    with pytest.raises(PlannedProviderError):
        config_service.test_connection(
            tenant_id="tenant-a",
            actor_roles=("tenant_admin",),
            configuration_id=result.id,
            connector=lambda _url, _secret: True,
        )


def test_configuration_referenced_by_strategy_cannot_be_deleted(
    config_service: ModelConfigurationService,
    session: Session,
) -> None:
    result = config_service.create(
        tenant_id="tenant-a",
        actor_roles=("tenant_admin",),
        command=configuration(),
    )
    session.add(
        StrategyModelReference(
            tenant_id="tenant-a",
            configuration_id=result.id,
            strategy_id="strategy-1",
        )
    )
    session.commit()

    with pytest.raises(ConfigurationInUseError):
        config_service.delete(
            tenant_id="tenant-a",
            actor_roles=("tenant_admin",),
            configuration_id=result.id,
        )

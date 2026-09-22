import pytest
from fastapi import FastAPI
from sqlalchemy.orm import Session
from trading.binance_runtime.lifecycle import (
    RuntimeRestoreError,
    find_system_account,
    restore_account_runtime,
)
from trading.main import runtime_lifespan
from trading.models import (
    AccountStatus,
    ConnectionStatus,
    CredentialType,
    MarketGroup,
    TradingAccount,
    TradingProvider,
)
from trading.secrets import InMemoryEncryptedSecretBackend


class FakeCandidate:
    def __init__(self, *, fail_validation: bool = False) -> None:
        self.fail_validation = fail_validation
        self.validate_count = 0
        self.stop_count = 0

    async def validate(self) -> object:
        self.validate_count += 1
        if self.fail_validation:
            raise RuntimeError("validation failed")
        return object()

    async def read_spot(self) -> object:
        return object()

    async def read_usdm(self) -> object:
        return object()

    async def stop(self) -> None:
        self.stop_count += 1


class FakeRuntimeManager:
    def __init__(self, candidate: FakeCandidate) -> None:
        self.candidate = candidate
        self.current = None
        self.credentials: tuple[str, str] | None = None
        self.stop_count = 0

    async def build_candidate(self, api_key: str, api_secret: str) -> FakeCandidate:
        self.credentials = (api_key, api_secret)
        return self.candidate

    async def replace(self, candidate: FakeCandidate) -> None:
        self.current = candidate

    async def stop(self) -> None:
        self.stop_count += 1
        if self.current is not None:
            await self.current.stop()
        self.current = None


def account(secret_ref: str, *, safe_permissions: bool = True) -> TradingAccount:
    return TradingAccount(
        tenant_id="tenant-a",
        alias="primary",
        market_group=MarketGroup.BINANCE,
        provider=TradingProvider.BINANCE,
        account_slot="primary",
        environment="production",
        credential_type=CredentialType.HMAC,
        secret_ref=secret_ref,
        status=AccountStatus.READ_ONLY,
        connection_status=ConnectionStatus.CONNECTED,
        trading_enabled=False,
        ip_restricted=True,
        can_read=True,
        can_withdraw=not safe_permissions,
        can_internal_transfer=False,
        can_universal_transfer=False,
        created_by="user-a",
    )


@pytest.mark.asyncio
async def test_restores_runtime_from_encrypted_persisted_credentials(
    session: Session,
) -> None:
    backend = InMemoryEncryptedSecretBackend()
    secret_ref = backend.put(
        "tenant-a",
        {"api_key": "stored-key", "private_key_or_secret": "stored-secret"},
    )
    stored_account = account(secret_ref)
    session.add(stored_account)
    session.commit()
    candidate = FakeCandidate()
    manager = FakeRuntimeManager(candidate)

    loaded = find_system_account(session)
    assert loaded is not None
    await restore_account_runtime(loaded, backend, manager)

    assert manager.credentials == ("stored-key", "stored-secret")
    assert manager.current is candidate
    assert candidate.validate_count == 1


@pytest.mark.asyncio
async def test_rejects_unsafe_persisted_permissions(session: Session) -> None:
    backend = InMemoryEncryptedSecretBackend()
    secret_ref = backend.put(
        "tenant-a",
        {"api_key": "stored-key", "private_key_or_secret": "stored-secret"},
    )
    stored_account = account(secret_ref, safe_permissions=False)
    session.add(stored_account)
    session.commit()
    manager = FakeRuntimeManager(FakeCandidate())

    with pytest.raises(RuntimeRestoreError, match="permissions are unsafe"):
        await restore_account_runtime(stored_account, backend, manager)

    assert manager.credentials is None


@pytest.mark.asyncio
async def test_validation_failure_stops_candidate(session: Session) -> None:
    backend = InMemoryEncryptedSecretBackend()
    secret_ref = backend.put(
        "tenant-a",
        {"api_key": "stored-key", "private_key_or_secret": "stored-secret"},
    )
    stored_account = account(secret_ref)
    session.add(stored_account)
    session.commit()
    candidate = FakeCandidate(fail_validation=True)
    manager = FakeRuntimeManager(candidate)

    with pytest.raises(RuntimeRestoreError, match="validation failed"):
        await restore_account_runtime(stored_account, backend, manager)

    assert candidate.stop_count == 1
    assert manager.current is None


@pytest.mark.asyncio
async def test_app_lifespan_restores_and_stops_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = FakeRuntimeManager(FakeCandidate())
    restore_count = 0

    async def restore(_: FakeRuntimeManager) -> bool:
        nonlocal restore_count
        restore_count += 1
        return True

    monkeypatch.setattr("trading.main.get_binance_runtime_manager", lambda: manager)
    monkeypatch.setattr("trading.main.restore_persisted_runtime", restore)

    async with runtime_lifespan(FastAPI()):
        assert restore_count == 1
        assert manager.stop_count == 0

    assert manager.stop_count == 1

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from trading.binance.errors import BinanceConnectorError
from trading.binance.permissions import AccountPermissionSnapshot
from trading.binance_account import BinanceAccountReplaceCommand, BinanceAccountService
from trading.binance_runtime.manager import RuntimeSwapError
from trading.models import TradingAccount
from trading.secrets import InMemoryEncryptedSecretBackend


class PermissionProbe:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail

    def inspect(self, **_: object) -> AccountPermissionSnapshot:
        if self.fail:
            raise BinanceConnectorError(
                "binance.credentials_invalid",
                "Binance credentials are invalid",
            )
        return AccountPermissionSnapshot(
            external_account_ref="binance-user-42",
            ip_restricted=True,
            can_read=True,
            can_spot_trade=True,
            can_margin_trade=False,
            can_futures_trade=True,
            can_withdraw=False,
            can_internal_transfer=False,
            can_universal_transfer=False,
        )


class FakeCandidate:
    def __init__(self, *, validation_error: Exception | None = None) -> None:
        self.validation_error = validation_error
        self.validate_count = 0
        self.stop_count = 0

    async def validate(self) -> object:
        self.validate_count += 1
        if self.validation_error is not None:
            raise self.validation_error
        return object()

    async def stop(self) -> None:
        self.stop_count += 1


class FakeRuntimeManager:
    def __init__(self, candidates: list[FakeCandidate]) -> None:
        self.candidates = candidates
        self.current: FakeCandidate | None = None
        self.build_count = 0
        self.fail_replace = False

    async def build_candidate(self, api_key: str, api_secret: str) -> FakeCandidate:
        del api_key, api_secret
        candidate = self.candidates[self.build_count]
        self.build_count += 1
        return candidate

    async def replace(self, candidate: FakeCandidate) -> None:
        if self.fail_replace:
            await candidate.stop()
            raise RuntimeSwapError("unable to replace Binance runtime")
        previous = self.current
        self.current = candidate
        if previous is not None:
            await previous.stop()


def command(alias: str, *, secret: str = "candidate-secret") -> BinanceAccountReplaceCommand:
    return BinanceAccountReplaceCommand(
        alias=alias,
        api_key="candidate-key",
        api_secret=secret,
        ip_whitelist_confirmed=True,
    )


def service(
    session: Session,
    backend: InMemoryEncryptedSecretBackend,
    manager: FakeRuntimeManager,
    *,
    probe: PermissionProbe | None = None,
) -> BinanceAccountService:
    return BinanceAccountService(
        session,
        backend,
        probe or PermissionProbe(),
        runtime_manager=manager,
    )


@pytest.mark.asyncio
async def test_permission_failure_does_not_build_runtime_or_store_account(
    session: Session,
) -> None:
    backend = InMemoryEncryptedSecretBackend()
    manager = FakeRuntimeManager([])
    account_service = service(
        session,
        backend,
        manager,
        probe=PermissionProbe(fail=True),
    )

    with pytest.raises(BinanceConnectorError) as error:
        await account_service.replace(
            tenant_id="tenant-a",
            actor_user_id="user-a",
            actor_roles=("tenant_admin",),
            command=command("candidate"),
        )

    assert error.value.code == "binance.credentials_invalid"
    assert manager.build_count == 0
    assert session.scalar(select(TradingAccount)) is None
    assert backend.count == 0


@pytest.mark.asyncio
async def test_candidate_validation_failure_preserves_existing_account(
    session: Session,
) -> None:
    backend = InMemoryEncryptedSecretBackend()
    current = FakeCandidate()
    candidate = FakeCandidate(validation_error=RuntimeError("candidate failed"))
    manager = FakeRuntimeManager([current, candidate])
    account_service = service(session, backend, manager)
    await account_service.replace(
        tenant_id="tenant-a",
        actor_user_id="user-a",
        actor_roles=("tenant_admin",),
        command=command("current"),
    )

    with pytest.raises(BinanceConnectorError) as error:
        await account_service.replace(
            tenant_id="tenant-a",
            actor_user_id="user-a",
            actor_roles=("tenant_admin",),
            command=command("candidate"),
        )

    stored = session.scalar(select(TradingAccount))
    assert error.value.code == "binance.runtime_not_ready"
    assert stored is not None
    assert stored.alias == "current"
    assert backend.count == 1
    assert manager.current is current
    assert candidate.stop_count == 1


@pytest.mark.asyncio
async def test_successful_replacement_switches_runtime_and_deletes_old_secret(
    session: Session,
) -> None:
    backend = InMemoryEncryptedSecretBackend()
    current = FakeCandidate()
    candidate = FakeCandidate()
    manager = FakeRuntimeManager([current, candidate])
    account_service = service(session, backend, manager)
    await account_service.replace(
        tenant_id="tenant-a",
        actor_user_id="user-a",
        actor_roles=("tenant_admin",),
        command=command("current"),
    )
    account_id = session.scalar(select(TradingAccount.id))

    await account_service.replace(
        tenant_id="tenant-a",
        actor_user_id="user-a",
        actor_roles=("tenant_admin",),
        command=command("candidate"),
    )

    stored = session.scalar(select(TradingAccount))
    assert stored is not None
    assert stored.id == account_id
    assert stored.alias == "candidate"
    assert manager.current is candidate
    assert current.stop_count == 1
    assert backend.count == 1


@pytest.mark.asyncio
async def test_runtime_switch_failure_restores_database_and_old_runtime(
    session: Session,
) -> None:
    backend = InMemoryEncryptedSecretBackend()
    current = FakeCandidate()
    candidate = FakeCandidate()
    manager = FakeRuntimeManager([current, candidate])
    account_service = service(session, backend, manager)
    await account_service.replace(
        tenant_id="tenant-a",
        actor_user_id="user-a",
        actor_roles=("tenant_admin",),
        command=command("current"),
    )
    old_secret_ref = session.scalar(select(TradingAccount.secret_ref))
    manager.fail_replace = True

    with pytest.raises(BinanceConnectorError) as error:
        await account_service.replace(
            tenant_id="tenant-a",
            actor_user_id="user-a",
            actor_roles=("tenant_admin",),
            command=command("candidate"),
        )

    stored = session.scalar(select(TradingAccount))
    assert error.value.code == "binance.runtime_not_ready"
    assert stored is not None
    assert stored.alias == "current"
    assert stored.secret_ref == old_secret_ref
    assert manager.current is current
    assert candidate.stop_count == 1
    assert backend.count == 1


@pytest.mark.asyncio
async def test_runtime_error_does_not_expose_candidate_secret(session: Session) -> None:
    secret = "never-log-this-secret"
    backend = InMemoryEncryptedSecretBackend()
    candidate = FakeCandidate(validation_error=RuntimeError(secret))
    manager = FakeRuntimeManager([candidate])
    account_service = service(session, backend, manager)
    payload = command("candidate", secret=secret)

    with pytest.raises(BinanceConnectorError) as error:
        await account_service.replace(
            tenant_id="tenant-a",
            actor_user_id="user-a",
            actor_roles=("tenant_admin",),
            command=payload,
        )

    assert secret not in str(error.value)
    assert secret not in repr(payload)

from sqlalchemy import select
from sqlalchemy.orm import Session

from trading.binance_runtime.ports import CandidateRuntime, RuntimeManager
from trading.config import get_settings
from trading.db import get_engine
from trading.models import TradingAccount, TradingProvider
from trading.secrets import LocalAesGcmSecretBackend, LocalCredentialVault, SecretBackend


class RuntimeRestoreError(RuntimeError):
    pass


def find_system_account(session: Session) -> TradingAccount | None:
    accounts = list(
        session.scalars(
            select(TradingAccount)
            .where(TradingAccount.provider == TradingProvider.BINANCE)
            .limit(2)
        )
    )
    if len(accounts) > 1:
        raise RuntimeRestoreError("multiple Binance account owners are configured")
    return accounts[0] if accounts else None


async def restore_account_runtime(
    account: TradingAccount,
    secret_backend: SecretBackend,
    runtime_manager: RuntimeManager,
) -> None:
    if account.environment != "demo":
        raise RuntimeRestoreError("only Binance Demo accounts can be restored")
    if not account.secret_ref:
        raise RuntimeRestoreError("Binance account credential reference is missing")
    if (
        not account.can_read
        or account.can_withdraw
        or account.can_internal_transfer
        or account.can_universal_transfer
    ):
        raise RuntimeRestoreError("Binance account permissions are unsafe")

    try:
        credential = secret_backend.get(account.tenant_id, account.secret_ref)
        api_key = credential["api_key"]
        api_secret = credential["private_key_or_secret"]
    except Exception:
        raise RuntimeRestoreError("Binance account credential is unavailable") from None

    candidate: CandidateRuntime | None = None
    try:
        candidate = await runtime_manager.build_candidate(api_key, api_secret)
        await candidate.validate()
    except Exception:
        await _stop_quietly(candidate)
        raise RuntimeRestoreError("Binance runtime validation failed") from None

    try:
        await runtime_manager.replace(candidate)
    except Exception:
        raise RuntimeRestoreError("Binance runtime restoration failed") from None


async def restore_persisted_runtime(runtime_manager: RuntimeManager) -> bool:
    with Session(get_engine(), expire_on_commit=False) as session:
        account = find_system_account(session)
        if account is None:
            await runtime_manager.stop()
            return False
        if account.environment != "demo":
            await runtime_manager.stop()
            return False
        settings = get_settings()
        try:
            vault = LocalCredentialVault.from_file(settings.binance_credential_master_key_file)
        except (FileNotFoundError, PermissionError, OSError, ValueError):
            raise RuntimeRestoreError("local credential master key is unavailable") from None
        secret_backend = LocalAesGcmSecretBackend(session, vault)
        await restore_account_runtime(account, secret_backend, runtime_manager)
        return True


async def _stop_quietly(candidate: CandidateRuntime | None) -> None:
    if candidate is None:
        return
    try:
        await candidate.stop()
    except Exception:
        return


__all__ = [
    "RuntimeRestoreError",
    "find_system_account",
    "restore_account_runtime",
    "restore_persisted_runtime",
]

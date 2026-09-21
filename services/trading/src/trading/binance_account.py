import hashlib
from collections.abc import Callable
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from trading.binance.errors import BinanceConnectorError
from trading.binance.permissions import AccountPermissionProbe, AccountPermissionSnapshot
from trading.binance_runtime.ports import CandidateRuntime, RuntimeManager
from trading.models import (
    AccountStatus,
    ConnectionStatus,
    CredentialType,
    MarketGroup,
    TradingAccount,
    TradingProvider,
    utc_now,
)
from trading.secrets import SecretBackend

ACCOUNT_REPLACEMENT_FIELDS = (
    "alias",
    "external_account_ref",
    "credential_type",
    "api_key_fingerprint",
    "secret_ref",
    "status",
    "connection_status",
    "trading_enabled",
    "is_active",
    "credential_version",
    "credential_confirmed_at",
    "credential_confirmed_by",
    "last_permission_check_at",
    "ip_restricted",
    "can_read",
    "can_spot_trade",
    "can_margin_trade",
    "can_futures_trade",
    "can_withdraw",
    "can_internal_transfer",
    "can_universal_transfer",
    "trading_authority_expiration_time_ms",
)


class BinanceAccountReplaceCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str = Field(min_length=1, max_length=120)
    api_key: SecretStr = Field(min_length=1)
    api_secret: SecretStr = Field(min_length=1)
    ip_whitelist_confirmed: bool

    @field_validator("alias")
    @classmethod
    def validate_alias(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("alias must not be blank")
        return normalized


class BinanceAccountView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str
    api_key_fingerprint: str
    connection_status: ConnectionStatus
    last_verified_at: datetime


class BinanceAccountService:
    def __init__(
        self,
        session: Session,
        secret_backend: SecretBackend,
        permission_probe: AccountPermissionProbe,
        *,
        runtime_manager: RuntimeManager | None = None,
        on_changed: Callable[[str], None] | None = None,
    ) -> None:
        self._session = session
        self._secret_backend = secret_backend
        self._permission_probe = permission_probe
        self._runtime_manager = runtime_manager
        self._on_changed = on_changed or (lambda _: None)

    def get(self, tenant_id: str) -> BinanceAccountView:
        account = self._find(tenant_id)
        if account is None:
            raise LookupError("Binance account is not bound")
        return self._view(account)

    async def replace(
        self,
        *,
        tenant_id: str,
        actor_user_id: str,
        actor_roles: tuple[str, ...],
        command: BinanceAccountReplaceCommand,
    ) -> BinanceAccountView:
        self._require_tenant_admin(actor_roles)
        if not command.ip_whitelist_confirmed:
            raise ValueError("Binance API key IP whitelist must be confirmed")

        api_key = command.api_key.get_secret_value()
        api_secret = command.api_secret.get_secret_value()
        permissions = self._inspect_permissions(api_key, api_secret)
        self._validate_permissions(permissions)
        candidate = await self._build_and_validate_candidate(api_key, api_secret)

        previous = self._find(tenant_id)
        previous_values = self._snapshot(previous) if previous is not None else None
        old_secret_ref = previous.secret_ref if previous is not None else None
        new_secret_ref = self._secret_backend.put(
            tenant_id,
            {"api_key": api_key, "private_key_or_secret": api_secret},
        )
        now = utc_now()
        account = previous or TradingAccount(
            tenant_id=tenant_id,
            market_group=MarketGroup.BINANCE,
            provider=TradingProvider.BINANCE,
            account_slot="primary",
            environment="production",
            created_by=actor_user_id,
        )
        account.alias = command.alias
        account.external_account_ref = permissions.external_account_ref
        account.credential_type = CredentialType.HMAC
        account.api_key_fingerprint = self._fingerprint(api_key)
        account.secret_ref = new_secret_ref
        account.status = AccountStatus.READ_ONLY
        account.connection_status = ConnectionStatus.CONNECTED
        account.trading_enabled = False
        account.is_active = False
        account.credential_version = 1
        account.credential_confirmed_at = now
        account.credential_confirmed_by = actor_user_id
        account.last_permission_check_at = now
        self._apply_permissions(account, permissions)
        if previous is None:
            self._session.add(account)

        try:
            self._session.commit()
        except Exception:
            self._session.rollback()
            self._secret_backend.delete(tenant_id, new_secret_ref)
            await self._stop_candidate(candidate)
            raise

        if candidate is not None and self._runtime_manager is not None:
            try:
                await self._runtime_manager.replace(candidate)
            except Exception:
                self._compensate_failed_switch(
                    account=account,
                    previous_values=previous_values,
                    new_secret_ref=new_secret_ref,
                )
                raise BinanceConnectorError(
                    "binance.runtime_not_ready",
                    "Binance runtime replacement failed",
                ) from None

        if old_secret_ref and old_secret_ref != new_secret_ref:
            self._secret_backend.delete(tenant_id, old_secret_ref)
        self._session.commit()
        self._on_changed(tenant_id)
        return self._view(account)

    async def delete(
        self,
        *,
        tenant_id: str,
        actor_roles: tuple[str, ...],
    ) -> None:
        self._require_tenant_admin(actor_roles)
        account = self._find(tenant_id)
        if account is None:
            raise LookupError("Binance account is not bound")
        if self._runtime_manager is not None:
            await self._runtime_manager.stop()
        if account.secret_ref:
            self._secret_backend.delete(tenant_id, account.secret_ref)
        self._session.delete(account)
        self._session.commit()
        self._on_changed(tenant_id)

    def _inspect_permissions(
        self,
        api_key: str,
        api_secret: str,
    ) -> AccountPermissionSnapshot:
        try:
            return self._permission_probe.inspect(
                api_key=api_key,
                api_secret=api_secret,
            )
        except BinanceConnectorError:
            raise
        except Exception:
            raise BinanceConnectorError(
                "binance.credentials_invalid",
                "Binance credentials or permissions could not be verified",
            ) from None

    async def _build_and_validate_candidate(
        self,
        api_key: str,
        api_secret: str,
    ) -> CandidateRuntime | None:
        if self._runtime_manager is None:
            return None
        candidate: CandidateRuntime | None = None
        try:
            candidate = await self._runtime_manager.build_candidate(api_key, api_secret)
            await candidate.validate()
            return candidate
        except Exception:
            await self._stop_candidate(candidate)
            raise BinanceConnectorError(
                "binance.runtime_not_ready",
                "Binance runtime validation failed",
            ) from None

    def _compensate_failed_switch(
        self,
        *,
        account: TradingAccount,
        previous_values: dict[str, object] | None,
        new_secret_ref: str,
    ) -> None:
        self._secret_backend.delete(account.tenant_id, new_secret_ref)
        if previous_values is None:
            self._session.delete(account)
        else:
            for field, value in previous_values.items():
                setattr(account, field, value)
        self._session.commit()

    @staticmethod
    def _snapshot(account: TradingAccount) -> dict[str, object]:
        return {field: getattr(account, field) for field in ACCOUNT_REPLACEMENT_FIELDS}

    @staticmethod
    async def _stop_candidate(candidate: CandidateRuntime | None) -> None:
        if candidate is None:
            return
        try:
            await candidate.stop()
        except Exception:
            return

    def _find(self, tenant_id: str) -> TradingAccount | None:
        return self._session.scalar(
            select(TradingAccount).where(
                TradingAccount.tenant_id == tenant_id,
                TradingAccount.provider == TradingProvider.BINANCE,
            )
        )

    @staticmethod
    def _validate_permissions(permissions: AccountPermissionSnapshot) -> None:
        if not permissions.can_read:
            raise ValueError("account read permission is required")
        if not permissions.ip_restricted:
            raise ValueError("API key IP restriction is required")
        if (
            permissions.can_withdraw
            or permissions.can_internal_transfer
            or permissions.can_universal_transfer
        ):
            raise ValueError("withdrawal and transfer permissions must be disabled")

    @staticmethod
    def _apply_permissions(
        account: TradingAccount,
        permissions: AccountPermissionSnapshot,
    ) -> None:
        account.ip_restricted = permissions.ip_restricted
        account.can_read = permissions.can_read
        account.can_spot_trade = permissions.can_spot_trade
        account.can_margin_trade = permissions.can_margin_trade
        account.can_futures_trade = permissions.can_futures_trade
        account.can_withdraw = permissions.can_withdraw
        account.can_internal_transfer = permissions.can_internal_transfer
        account.can_universal_transfer = permissions.can_universal_transfer
        account.trading_authority_expiration_time_ms = (
            permissions.trading_authority_expiration_time_ms
        )

    @staticmethod
    def _fingerprint(api_key: str) -> str:
        return f"sha256:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"

    @staticmethod
    def _require_tenant_admin(actor_roles: tuple[str, ...]) -> None:
        if "tenant_admin" not in actor_roles:
            raise PermissionError("tenant administrator role is required")

    @staticmethod
    def _view(account: TradingAccount) -> BinanceAccountView:
        if account.api_key_fingerprint is None or account.last_permission_check_at is None:
            raise ValueError("Binance account verification metadata is unavailable")
        return BinanceAccountView(
            alias=account.alias,
            api_key_fingerprint=account.api_key_fingerprint,
            connection_status=account.connection_status,
            last_verified_at=account.last_permission_check_at,
        )


__all__ = [
    "BinanceAccountReplaceCommand",
    "BinanceAccountService",
    "BinanceAccountView",
]

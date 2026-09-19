import hashlib
from datetime import UTC, datetime, timedelta
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from trading.models import (
    AccountScopeType,
    AccountStatus,
    ConnectionStatus,
    CredentialType,
    MarketGroup,
    TradingAccount,
    TradingAccountScope,
    TradingProvider,
    utc_now,
)
from trading.outbox import SqlOutboxPublisher
from trading.secrets import SecretBackend

PROVIDERS_BY_MARKET = {
    MarketGroup.CN_EQUITY: {TradingProvider.TONGHUASHUN, TradingProvider.CAIXIN},
    MarketGroup.HK_US_EQUITY: {TradingProvider.FUTU, TradingProvider.LONGBRIDGE},
    MarketGroup.BINANCE: {TradingProvider.BINANCE},
}


class AccountPermissionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_account_ref: str
    can_read: bool
    can_spot_trade: bool
    can_margin_trade: bool
    can_futures_trade: bool
    can_withdraw: bool


class AccountPermissionProbe(Protocol):
    def inspect(
        self,
        *,
        credential_type: CredentialType,
        api_key: str,
        private_key_or_secret: str,
        scopes: tuple[AccountScopeType, ...],
        isolated_symbols: tuple[str, ...],
    ) -> AccountPermissionSnapshot: ...


class AccountBindCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str = Field(min_length=1, max_length=120)
    market_group: MarketGroup
    provider: TradingProvider
    environment: str = "production"
    credential_type: CredentialType | None = None
    api_key: SecretStr | None = None
    private_key_or_secret: SecretStr | None = None
    enabled_scopes: list[AccountScopeType] = Field(default_factory=list)
    isolated_symbols: list[str] = Field(default_factory=list)
    ip_whitelist_confirmed: bool = False

    @model_validator(mode="after")
    def validate_account_contract(self) -> "AccountBindCommand":
        if self.provider not in PROVIDERS_BY_MARKET[self.market_group]:
            raise ValueError("provider is not allowed for this market group")
        if self.environment != "production":
            raise ValueError("only production accounts are supported")
        if self.market_group is not MarketGroup.BINANCE:
            return self
        if (
            self.credential_type is None
            or self.api_key is None
            or self.private_key_or_secret is None
        ):
            raise ValueError("binance credentials are required")
        if not self.enabled_scopes:
            raise ValueError("at least one binance scope is required")
        if not self.ip_whitelist_confirmed:
            raise ValueError("fixed egress IP whitelist must be confirmed")
        if AccountScopeType.ISOLATED_MARGIN in self.enabled_scopes and not self.isolated_symbols:
            raise ValueError("isolated symbols are required")
        normalized_symbols = [symbol.strip().upper() for symbol in self.isolated_symbols]
        if any(not symbol.isalnum() for symbol in normalized_symbols):
            raise ValueError("isolated symbols must be alphanumeric")
        self.isolated_symbols = list(dict.fromkeys(normalized_symbols))
        self.enabled_scopes = list(dict.fromkeys(self.enabled_scopes))
        return self


class AccountScopeView(BaseModel):
    scope_type: AccountScopeType
    scope_key: str
    symbol: str | None
    enabled: bool
    status: str


class TradingAccountView(BaseModel):
    id: str
    tenant_id: str
    alias: str
    market_group: MarketGroup
    provider: TradingProvider
    environment: str
    external_account_ref: str | None
    credential_type: CredentialType | None
    api_key_fingerprint: str | None
    credential_status: str
    status: AccountStatus
    connection_status: ConnectionStatus
    trading_enabled: bool
    permissions: AccountPermissionSnapshot | None
    scopes: list[AccountScopeView]
    last_permission_check_at: datetime | None
    last_synced_at: datetime | None


class TradingAccountService:
    def __init__(
        self,
        session: Session,
        secret_backend: SecretBackend,
        permission_probe: AccountPermissionProbe,
    ) -> None:
        self.session = session
        self.secret_backend = secret_backend
        self.permission_probe = permission_probe
        self.outbox = SqlOutboxPublisher(session)

    def bind(
        self,
        *,
        tenant_id: str,
        actor_roles: tuple[str, ...],
        mfa_verified_at: datetime | None,
        command: AccountBindCommand,
        actor_user_id: str = "system",
    ) -> TradingAccountView:
        self._require_tenant_admin(actor_roles)
        if command.market_group is not MarketGroup.BINANCE:
            return self._bind_pending_account(tenant_id, actor_user_id, command)

        self._require_recent_mfa(mfa_verified_at)
        credentials = self._credentials(command)
        credential_type = command.credential_type
        if credential_type is None:
            raise ValueError("binance credential type is required")
        permissions = self.permission_probe.inspect(
            credential_type=credential_type,
            api_key=credentials["api_key"],
            private_key_or_secret=credentials["private_key_or_secret"],
            scopes=tuple(command.enabled_scopes),
            isolated_symbols=tuple(command.isolated_symbols),
        )
        self._validate_read_permissions(permissions)

        secret_ref = self.secret_backend.put(tenant_id, credentials)
        account = TradingAccount(
            tenant_id=tenant_id,
            alias=command.alias.strip(),
            market_group=command.market_group,
            provider=command.provider,
            environment=command.environment,
            external_account_ref=permissions.external_account_ref,
            credential_type=command.credential_type,
            api_key_fingerprint=self._fingerprint(credentials["api_key"]),
            secret_ref=secret_ref,
            status=AccountStatus.READ_ONLY,
            connection_status=ConnectionStatus.CONNECTED,
            trading_enabled=False,
            can_read=permissions.can_read,
            can_spot_trade=permissions.can_spot_trade,
            can_margin_trade=permissions.can_margin_trade,
            can_futures_trade=permissions.can_futures_trade,
            can_withdraw=permissions.can_withdraw,
            last_permission_check_at=utc_now(),
            last_synced_at=utc_now(),
            created_by=actor_user_id,
        )
        self.session.add(account)
        self.session.flush()
        scopes = self._scope_records(tenant_id, account.id, command)
        self.session.add_all(scopes)
        self._publish_account(account, "trading.account.bound")
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            self.secret_backend.delete(tenant_id, secret_ref)
            raise
        return self._view(account, scopes)

    def list_for_tenant(self, tenant_id: str) -> list[TradingAccountView]:
        accounts = list(
            self.session.scalars(
                select(TradingAccount)
                .where(TradingAccount.tenant_id == tenant_id)
                .order_by(TradingAccount.alias)
            )
        )
        return [self._view(account, self._scopes(tenant_id, account.id)) for account in accounts]

    def enable_trading(
        self,
        *,
        tenant_id: str,
        account_id: str,
        actor_roles: tuple[str, ...],
        mfa_verified_at: datetime | None,
    ) -> TradingAccountView:
        self._require_tenant_admin(actor_roles)
        self._require_recent_mfa(mfa_verified_at)
        account = self._get(tenant_id, account_id)
        scopes = self._scopes(tenant_id, account_id)
        if (
            account.last_permission_check_at is None
            or utc_now() - account.last_permission_check_at > timedelta(minutes=5)
        ):
            raise ValueError("a recent account permission check is required")
        self._validate_trading_permissions(
            [scope.scope_type for scope in scopes],
            self._permission_snapshot(account),
        )
        account.trading_enabled = True
        account.status = AccountStatus.ACTIVE
        for scope in scopes:
            scope.enabled = True
        self._publish_account(account, "trading.account.enabled")
        self.session.commit()
        return self._view(account, scopes)

    def test_connection(
        self,
        *,
        tenant_id: str,
        account_id: str,
        actor_roles: tuple[str, ...],
    ) -> TradingAccountView:
        self._require_tenant_admin(actor_roles)
        account = self._get(tenant_id, account_id)
        if account.provider is not TradingProvider.BINANCE:
            raise ValueError("broker connector authorization is still pending")
        scopes = self._scopes(tenant_id, account_id)
        credentials = self._credentials_for(account)
        credential_type = account.credential_type
        if credential_type is None:
            raise ValueError("account credential type is unavailable")
        permissions = self.permission_probe.inspect(
            credential_type=credential_type,
            api_key=credentials["api_key"],
            private_key_or_secret=credentials["private_key_or_secret"],
            scopes=tuple(scope.scope_type for scope in scopes),
            isolated_symbols=tuple(
                scope.symbol
                for scope in scopes
                if scope.scope_type is AccountScopeType.ISOLATED_MARGIN and scope.symbol is not None
            ),
        )
        account.last_permission_check_at = utc_now()
        self._apply_permissions(account, permissions)
        if permissions.can_withdraw:
            account.status = AccountStatus.DISABLED
            account.connection_status = ConnectionStatus.ERROR
            account.trading_enabled = False
            for scope in scopes:
                scope.enabled = False
            self._publish_account(account, "trading.account.disabled")
            self.session.commit()
            raise ValueError("withdrawal permission is forbidden")
        self._validate_read_permissions(permissions)
        account.connection_status = ConnectionStatus.CONNECTED
        if account.status is AccountStatus.DISABLED:
            account.status = AccountStatus.READ_ONLY
        self._publish_account(account, "trading.account.connection_tested")
        self.session.commit()
        return self._view(account, scopes)

    def disconnect(
        self,
        *,
        tenant_id: str,
        account_id: str,
        actor_roles: tuple[str, ...],
    ) -> TradingAccountView:
        self._require_tenant_admin(actor_roles)
        account = self._get(tenant_id, account_id)
        scopes = self._scopes(tenant_id, account_id)
        account.connection_status = ConnectionStatus.DISCONNECTED
        account.trading_enabled = False
        account.status = AccountStatus.READ_ONLY
        for scope in scopes:
            scope.enabled = False
        self._publish_account(account, "trading.account.disconnected")
        self.session.commit()
        return self._view(account, scopes)

    def _bind_pending_account(
        self,
        tenant_id: str,
        actor_user_id: str,
        command: AccountBindCommand,
    ) -> TradingAccountView:
        account = TradingAccount(
            tenant_id=tenant_id,
            alias=command.alias.strip(),
            market_group=command.market_group,
            provider=command.provider,
            environment=command.environment,
            status=AccountStatus.PENDING_AUTHORIZATION,
            connection_status=ConnectionStatus.DISCONNECTED,
            trading_enabled=False,
            created_by=actor_user_id,
        )
        self.session.add(account)
        self.session.flush()
        self._publish_account(account, "trading.account.pending_authorization")
        self.session.commit()
        return self._view(account, [])

    def _get(self, tenant_id: str, account_id: str) -> TradingAccount:
        account = self.session.scalar(
            select(TradingAccount).where(
                TradingAccount.id == account_id,
                TradingAccount.tenant_id == tenant_id,
            )
        )
        if account is None:
            raise LookupError("trading account not found")
        return account

    def _scopes(self, tenant_id: str, account_id: str) -> list[TradingAccountScope]:
        return list(
            self.session.scalars(
                select(TradingAccountScope)
                .where(
                    TradingAccountScope.tenant_id == tenant_id,
                    TradingAccountScope.account_id == account_id,
                )
                .order_by(TradingAccountScope.scope_type, TradingAccountScope.scope_key)
            )
        )

    @staticmethod
    def _scope_records(
        tenant_id: str,
        account_id: str,
        command: AccountBindCommand,
    ) -> list[TradingAccountScope]:
        records: list[TradingAccountScope] = []
        for scope in command.enabled_scopes:
            symbols = (
                command.isolated_symbols if scope is AccountScopeType.ISOLATED_MARGIN else [None]
            )
            for symbol in symbols:
                records.append(
                    TradingAccountScope(
                        tenant_id=tenant_id,
                        account_id=account_id,
                        scope_type=scope,
                        scope_key=symbol or "global",
                        symbol=symbol,
                        enabled=False,
                        status="verified",
                    )
                )
        return records

    @staticmethod
    def _validate_read_permissions(
        permissions: AccountPermissionSnapshot,
    ) -> None:
        if permissions.can_withdraw:
            raise ValueError("withdrawal permission is forbidden")
        if not permissions.can_read:
            raise ValueError("account read permission is required")

    @classmethod
    def _validate_trading_permissions(
        cls,
        scopes: list[AccountScopeType],
        permissions: AccountPermissionSnapshot,
    ) -> None:
        cls._validate_read_permissions(permissions)
        checks = {
            AccountScopeType.SPOT: permissions.can_spot_trade,
            AccountScopeType.CROSS_MARGIN: permissions.can_margin_trade,
            AccountScopeType.ISOLATED_MARGIN: permissions.can_margin_trade,
            AccountScopeType.USDM_FUTURES: permissions.can_futures_trade,
        }
        if missing := [scope.value for scope in scopes if not checks[scope]]:
            raise ValueError(f"missing trading permissions for scopes: {', '.join(missing)}")

    @staticmethod
    def _credentials(command: AccountBindCommand) -> dict[str, str]:
        if (
            command.credential_type is None
            or command.api_key is None
            or command.private_key_or_secret is None
        ):
            raise ValueError("binance credentials are required")
        return {
            "api_key": command.api_key.get_secret_value(),
            "private_key_or_secret": command.private_key_or_secret.get_secret_value(),
        }

    def _credentials_for(self, account: TradingAccount) -> dict[str, str]:
        if account.secret_ref is None or account.credential_type is None:
            raise ValueError("account credentials are unavailable")
        return self.secret_backend.get(account.tenant_id, account.secret_ref)

    @staticmethod
    def _require_tenant_admin(actor_roles: tuple[str, ...]) -> None:
        if "tenant_admin" not in actor_roles:
            raise PermissionError("tenant administrator role is required")

    @staticmethod
    def _require_recent_mfa(verified_at: datetime | None) -> None:
        if verified_at is None:
            raise PermissionError("recent MFA verification is required")
        normalized = verified_at if verified_at.tzinfo else verified_at.replace(tzinfo=UTC)
        if datetime.now(UTC) - normalized > timedelta(minutes=5):
            raise PermissionError("recent MFA verification is required")

    @staticmethod
    def _fingerprint(api_key: str) -> str:
        return f"sha256:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"

    @staticmethod
    def _permission_snapshot(account: TradingAccount) -> AccountPermissionSnapshot:
        return AccountPermissionSnapshot(
            external_account_ref=account.external_account_ref or "",
            can_read=account.can_read,
            can_spot_trade=account.can_spot_trade,
            can_margin_trade=account.can_margin_trade,
            can_futures_trade=account.can_futures_trade,
            can_withdraw=account.can_withdraw,
        )

    @staticmethod
    def _apply_permissions(
        account: TradingAccount,
        permissions: AccountPermissionSnapshot,
    ) -> None:
        account.external_account_ref = permissions.external_account_ref
        account.can_read = permissions.can_read
        account.can_spot_trade = permissions.can_spot_trade
        account.can_margin_trade = permissions.can_margin_trade
        account.can_futures_trade = permissions.can_futures_trade
        account.can_withdraw = permissions.can_withdraw

    def _publish_account(self, account: TradingAccount, event_type: str) -> None:
        self.outbox.publish(
            tenant_id=account.tenant_id,
            event_type=event_type,
            aggregate_type="trading_account",
            aggregate_id=account.id,
            payload={
                "account_id": account.id,
                "provider": account.provider.value,
                "status": account.status.value,
                "connection_status": account.connection_status.value,
                "trading_enabled": account.trading_enabled,
            },
        )

    def _view(
        self,
        account: TradingAccount,
        scopes: list[TradingAccountScope],
    ) -> TradingAccountView:
        permissions = (
            self._permission_snapshot(account)
            if account.provider is TradingProvider.BINANCE
            else None
        )
        return TradingAccountView(
            id=account.id,
            tenant_id=account.tenant_id,
            alias=account.alias,
            market_group=account.market_group,
            provider=account.provider,
            environment=account.environment,
            external_account_ref=account.external_account_ref,
            credential_type=account.credential_type,
            api_key_fingerprint=account.api_key_fingerprint,
            credential_status="configured" if account.secret_ref else "pending",
            status=account.status,
            connection_status=account.connection_status,
            trading_enabled=account.trading_enabled,
            permissions=permissions,
            scopes=[
                AccountScopeView(
                    scope_type=scope.scope_type,
                    scope_key=scope.scope_key,
                    symbol=scope.symbol,
                    enabled=scope.enabled,
                    status=scope.status,
                )
                for scope in scopes
            ],
            last_permission_check_at=account.last_permission_check_at,
            last_synced_at=account.last_synced_at,
        )


__all__ = [
    "AccountBindCommand",
    "AccountPermissionSnapshot",
    "CredentialType",
    "TradingAccountService",
]

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from trading.binance.client import BinanceCredentials
from trading.binance.errors import BinanceConnectorError, BinanceWriteTimeout
from trading.models import (
    AccountScopeType,
    AccountStatus,
    ConnectionStatus,
    CredentialType,
    KillSwitch,
    TradingAccount,
    TradingAccountScope,
    TradingOperation,
    utc_now,
)
from trading.orders import IdempotencyConflictError, TradingGuardError
from trading.outbox import SqlOutboxPublisher
from trading.risk import RiskAuthorizer
from trading.secrets import SecretBackend


class AccountConnector(Protocol):
    def account_snapshot(
        self,
        *,
        scope: AccountScopeType,
        credentials: BinanceCredentials,
        isolated_symbols: tuple[str, ...] = (),
    ) -> dict[str, Any]: ...

    def margin_borrow_repay(
        self,
        *,
        scope: AccountScopeType,
        asset: str,
        amount: str,
        action: str,
        credentials: BinanceCredentials,
        isolated_symbol: str | None = None,
    ) -> str: ...

    def set_futures_leverage(
        self,
        *,
        symbol: str,
        leverage: int,
        credentials: BinanceCredentials,
    ) -> dict[str, Any]: ...


class MarginTransactionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1, max_length=36)
    account_scope: AccountScopeType
    symbol: str | None = Field(default=None, max_length=40)
    asset: str = Field(min_length=2, max_length=20, pattern=r"^[A-Za-z0-9]+$")
    amount: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def validate_margin_scope(self) -> "MarginTransactionCommand":
        if self.account_scope not in {
            AccountScopeType.CROSS_MARGIN,
            AccountScopeType.ISOLATED_MARGIN,
        }:
            raise ValueError("margin transaction requires a margin scope")
        if self.account_scope is AccountScopeType.ISOLATED_MARGIN and not self.symbol:
            raise ValueError("isolated margin transaction requires a symbol")
        self.asset = self.asset.upper()
        self.symbol = self.symbol.upper() if self.symbol else None
        return self


class FuturesLeverageCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1, max_length=36)
    symbol: str = Field(min_length=3, max_length=40, pattern=r"^[A-Za-z0-9]+$")
    leverage: int = Field(ge=1, le=125)

    @model_validator(mode="after")
    def normalize_symbol(self) -> "FuturesLeverageCommand":
        self.symbol = self.symbol.upper()
        return self


class AccountSnapshotView(BaseModel):
    account_id: str
    account_scope: AccountScopeType
    fetched_at: datetime
    data: dict[str, Any]


class TradingOperationView(BaseModel):
    id: str
    account_id: str
    operation_type: str
    account_scope: AccountScopeType
    symbol: str | None
    status: str
    broker_reference: str | None
    error_code: str | None
    created_at: datetime
    updated_at: datetime


class AccountOperationsService:
    def __init__(
        self,
        session: Session,
        secret_backend: SecretBackend,
        connector: AccountConnector,
        risk_authorizer: RiskAuthorizer,
        *,
        max_futures_leverage: int = 20,
    ) -> None:
        self.session = session
        self.secret_backend = secret_backend
        self.connector = connector
        self.risk_authorizer = risk_authorizer
        self.max_futures_leverage = max_futures_leverage
        self.outbox = SqlOutboxPublisher(session)

    def snapshot(
        self,
        *,
        tenant_id: str,
        account_id: str,
        scope: AccountScopeType,
        symbol: str | None = None,
    ) -> AccountSnapshotView:
        account = self._account(tenant_id, account_id)
        if not account.can_read or account.connection_status is ConnectionStatus.DISCONNECTED:
            raise TradingGuardError("account is not connected for read access")
        scope_record = self._scope(
            tenant_id,
            account_id,
            scope,
            symbol,
            require_enabled=False,
        )
        isolated_symbols = (
            (scope_record.symbol,)
            if scope is AccountScopeType.ISOLATED_MARGIN and scope_record.symbol
            else ()
        )
        fetched_at = utc_now()
        data = self.connector.account_snapshot(
            scope=scope,
            credentials=self._credentials(account),
            isolated_symbols=isolated_symbols,
        )
        account.last_synced_at = fetched_at
        scope_record.last_synced_at = fetched_at
        self.session.commit()
        return AccountSnapshotView(
            account_id=account.id,
            account_scope=scope,
            fetched_at=fetched_at,
            data=data,
        )

    def margin_transaction(
        self,
        *,
        tenant_id: str,
        actor_roles: tuple[str, ...],
        mfa_verified_at: datetime | None,
        idempotency_key: str,
        risk_approval_token: str,
        action: str,
        command: MarginTransactionCommand,
    ) -> TradingOperationView:
        normalized_action = action.upper()
        if normalized_action not in {"BORROW", "REPAY"}:
            raise ValueError("margin action must be BORROW or REPAY")
        self._require_trader_and_mfa(actor_roles, mfa_verified_at)
        account = self._account(tenant_id, command.account_id)
        self._scope(
            tenant_id,
            account.id,
            command.account_scope,
            command.symbol,
            require_enabled=normalized_action == "BORROW",
        )
        if normalized_action == "BORROW":
            self._require_risk_increase_allowed(
                tenant_id,
                account,
                command.model_dump(mode="json"),
                risk_approval_token,
            )
        operation_type = f"margin_{normalized_action.lower()}"
        operation, is_new = self._prepare_operation(
            tenant_id=tenant_id,
            account=account,
            operation_type=operation_type,
            scope=command.account_scope,
            symbol=command.symbol,
            idempotency_key=idempotency_key,
            payload={"action": normalized_action, **command.model_dump(mode="json")},
        )
        if not is_new:
            return self._view(operation)
        return self._run_operation(
            operation,
            lambda: self.connector.margin_borrow_repay(
                scope=command.account_scope,
                asset=command.asset,
                amount=str(command.amount),
                action=normalized_action,
                credentials=self._credentials(account),
                isolated_symbol=command.symbol,
            ),
        )

    def set_futures_leverage(
        self,
        *,
        tenant_id: str,
        actor_roles: tuple[str, ...],
        mfa_verified_at: datetime | None,
        idempotency_key: str,
        risk_approval_token: str,
        command: FuturesLeverageCommand,
    ) -> TradingOperationView:
        self._require_trader_and_mfa(actor_roles, mfa_verified_at)
        if command.leverage > self.max_futures_leverage:
            raise ValueError(f"platform leverage limit is {self.max_futures_leverage}")
        account = self._account(tenant_id, command.account_id)
        self._scope(
            tenant_id,
            account.id,
            AccountScopeType.USDM_FUTURES,
            None,
            require_enabled=True,
        )
        self._require_risk_increase_allowed(
            tenant_id,
            account,
            command.model_dump(mode="json"),
            risk_approval_token,
        )
        operation, is_new = self._prepare_operation(
            tenant_id=tenant_id,
            account=account,
            operation_type="futures_leverage",
            scope=AccountScopeType.USDM_FUTURES,
            symbol=command.symbol,
            idempotency_key=idempotency_key,
            payload=command.model_dump(mode="json"),
        )
        if not is_new:
            return self._view(operation)

        def update_leverage() -> str:
            result = self.connector.set_futures_leverage(
                symbol=command.symbol,
                leverage=command.leverage,
                credentials=self._credentials(account),
            )
            return f"{result['symbol']}:{result['leverage']}"

        return self._run_operation(operation, update_leverage)

    def _prepare_operation(
        self,
        *,
        tenant_id: str,
        account: TradingAccount,
        operation_type: str,
        scope: AccountScopeType,
        symbol: str | None,
        idempotency_key: str,
        payload: dict[str, Any],
    ) -> tuple[TradingOperation, bool]:
        if not idempotency_key or len(idempotency_key) > 80:
            raise ValueError("a valid idempotency key is required")
        fingerprint = self._fingerprint(payload)
        existing = self.session.scalar(
            select(TradingOperation).where(
                TradingOperation.tenant_id == tenant_id,
                TradingOperation.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise IdempotencyConflictError("idempotency key payload conflict")
            return existing, False
        operation = TradingOperation(
            tenant_id=tenant_id,
            account_id=account.id,
            operation_type=operation_type,
            account_scope=scope,
            symbol=symbol,
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
            status="pending",
        )
        self.session.add(operation)
        self.session.flush()
        self._publish_operation(operation, "trading.operation.requested")
        self.session.commit()
        return operation, True

    def _run_operation(
        self,
        operation: TradingOperation,
        execute: Callable[[], str],
    ) -> TradingOperationView:
        try:
            operation.broker_reference = execute()
            operation.status = "completed"
        except BinanceWriteTimeout as error:
            operation.status = "unknown"
            operation.error_code = error.code
        except BinanceConnectorError as error:
            operation.status = "rejected"
            operation.error_code = error.code
        self._publish_operation(operation, "trading.operation.status_changed")
        self.session.commit()
        return self._view(operation)

    def _account(self, tenant_id: str, account_id: str) -> TradingAccount:
        account = self.session.scalar(
            select(TradingAccount).where(
                TradingAccount.id == account_id,
                TradingAccount.tenant_id == tenant_id,
            )
        )
        if account is None:
            raise LookupError("trading account not found")
        return account

    def _scope(
        self,
        tenant_id: str,
        account_id: str,
        scope: AccountScopeType,
        symbol: str | None,
        *,
        require_enabled: bool,
    ) -> TradingAccountScope:
        scope_key = (
            symbol.upper() if scope is AccountScopeType.ISOLATED_MARGIN and symbol else "global"
        )
        conditions = [
            TradingAccountScope.tenant_id == tenant_id,
            TradingAccountScope.account_id == account_id,
            TradingAccountScope.scope_type == scope,
            TradingAccountScope.scope_key == scope_key,
        ]
        if require_enabled:
            conditions.append(TradingAccountScope.enabled.is_(True))
        record = self.session.scalar(select(TradingAccountScope).where(*conditions))
        if record is None:
            raise TradingGuardError("account scope is not available")
        return record

    def _require_risk_increase_allowed(
        self,
        tenant_id: str,
        account: TradingAccount,
        payload: dict[str, Any],
        approval_token: str,
    ) -> None:
        if account.status is not AccountStatus.ACTIVE or not account.trading_enabled:
            raise TradingGuardError("trading account is not enabled")
        switch = self.session.scalar(
            select(KillSwitch.id).where(
                KillSwitch.tenant_id == tenant_id,
                KillSwitch.active.is_(True),
            )
        )
        if switch is not None:
            raise TradingGuardError("trading kill switch is active")
        if not self.risk_authorizer.authorize(
            tenant_id=tenant_id,
            account_id=account.id,
            order=payload,
            approval_token=approval_token,
        ):
            raise TradingGuardError("risk approval is required")

    def _credentials(self, account: TradingAccount) -> BinanceCredentials:
        if account.secret_ref is None or account.credential_type is None:
            raise TradingGuardError("account credentials are unavailable")
        values = self.secret_backend.get(account.tenant_id, account.secret_ref)
        return BinanceCredentials(
            api_key=values["api_key"],
            private_key_or_secret=values["private_key_or_secret"],
            credential_type=CredentialType(account.credential_type),
        )

    @staticmethod
    def _fingerprint(payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode()).hexdigest()

    def _publish_operation(
        self,
        operation: TradingOperation,
        event_type: str,
    ) -> None:
        self.outbox.publish(
            tenant_id=operation.tenant_id,
            event_type=event_type,
            aggregate_type="trading_operation",
            aggregate_id=operation.id,
            payload={
                "operation_id": operation.id,
                "account_id": operation.account_id,
                "operation_type": operation.operation_type,
                "account_scope": operation.account_scope.value,
                "symbol": operation.symbol,
                "status": operation.status,
                "error_code": operation.error_code,
            },
        )

    @staticmethod
    def _require_trader_and_mfa(
        actor_roles: tuple[str, ...],
        mfa_verified_at: datetime | None,
    ) -> None:
        if not {"tenant_admin", "trader"}.intersection(actor_roles):
            raise PermissionError("trader role is required")
        if mfa_verified_at is None:
            raise PermissionError("recent MFA verification is required")
        normalized = (
            mfa_verified_at if mfa_verified_at.tzinfo else mfa_verified_at.replace(tzinfo=UTC)
        )
        if datetime.now(UTC) - normalized > timedelta(minutes=5):
            raise PermissionError("recent MFA verification is required")

    @staticmethod
    def _view(operation: TradingOperation) -> TradingOperationView:
        return TradingOperationView(
            id=operation.id,
            account_id=operation.account_id,
            operation_type=operation.operation_type,
            account_scope=operation.account_scope,
            symbol=operation.symbol,
            status=operation.status,
            broker_reference=operation.broker_reference,
            error_code=operation.error_code,
            created_at=operation.created_at,
            updated_at=operation.updated_at,
        )

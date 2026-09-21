import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal
from time import monotonic
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from trading.binance.errors import BinanceConnectorError
from trading.binance_account import BinanceAccountView
from trading.models import TradingAccount, TradingProvider, utc_now


class ProblemSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class OverviewSection[T](BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "error"]
    data: T | None
    error: ProblemSummary | None = None


class BinancePermissionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    can_read: bool
    can_spot_trade: bool
    can_futures_trade: bool
    ip_restricted: bool
    can_withdraw: bool
    can_internal_transfer: bool
    can_universal_transfer: bool


class SpotBalance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str
    free: Decimal
    locked: Decimal
    total: Decimal


class SpotAccountSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    balances: list[SpotBalance]
    as_of: datetime


class UsdmBalance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str
    wallet_balance: Decimal
    available_balance: Decimal
    unrealized_pnl: Decimal


class UsdmPosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    side: Literal["long", "short", "flat"]
    quantity: Decimal
    entry_price: Decimal
    mark_price: Decimal | None
    unrealized_pnl: Decimal | None
    leverage: int | None
    margin_mode: Literal["cross", "isolated"] | None


class UsdmAccountSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    balances: list[UsdmBalance]
    positions: list[UsdmPosition]
    as_of: datetime


class BinanceOverview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account: BinanceAccountView
    permissions: OverviewSection[BinancePermissionView]
    spot: OverviewSection[SpotAccountSnapshot]
    usdm: OverviewSection[UsdmAccountSnapshot]
    as_of: datetime


class RuntimeReader(Protocol):
    async def read_spot(self) -> SpotAccountSnapshot: ...

    async def read_usdm(self) -> UsdmAccountSnapshot: ...


class RuntimeProvider(Protocol):
    @property
    def current(self) -> RuntimeReader | None: ...


class BinanceOverviewCache:
    def __init__(self) -> None:
        self._values: dict[str, tuple[float, BinanceOverview]] = {}

    def get(self, tenant_id: str) -> tuple[float, BinanceOverview] | None:
        return self._values.get(tenant_id)

    def set(self, tenant_id: str, timestamp: float, overview: BinanceOverview) -> None:
        self._values[tenant_id] = (timestamp, overview)

    def invalidate(self, tenant_id: str) -> None:
        self._values.pop(tenant_id, None)


class BinanceOverviewService:
    def __init__(
        self,
        session: Session,
        runtime_manager: RuntimeProvider,
        *,
        cache_ttl_seconds: float = 5,
        clock: Callable[[], float] = monotonic,
        cache: BinanceOverviewCache | None = None,
    ) -> None:
        self._session = session
        self._runtime_manager = runtime_manager
        self._cache_ttl_seconds = cache_ttl_seconds
        self._clock = clock
        self._cache = cache or BinanceOverviewCache()

    async def get(self, tenant_id: str, *, refresh: bool = False) -> BinanceOverview:
        account = self._session.scalar(
            select(TradingAccount).where(
                TradingAccount.tenant_id == tenant_id,
                TradingAccount.provider == TradingProvider.BINANCE,
            )
        )
        if account is None:
            raise LookupError("Binance account is not bound")

        cached = self._cache.get(tenant_id)
        if (
            not refresh
            and cached is not None
            and self._clock() - cached[0] < self._cache_ttl_seconds
        ):
            return cached[1]

        account_view = self._account_view(account)
        permissions = OverviewSection[BinancePermissionView](
            status="ok",
            data=self._permissions_view(account),
        )
        runtime = self._runtime_manager.current
        spot: OverviewSection[SpotAccountSnapshot]
        usdm: OverviewSection[UsdmAccountSnapshot]
        if runtime is None:
            spot = self._error_section("binance.runtime_not_ready")
            usdm = self._error_section("binance.runtime_not_ready")
        else:
            spot, usdm = await asyncio.gather(
                self._spot_section(runtime.read_spot()),
                self._usdm_section(runtime.read_usdm()),
            )

        overview = BinanceOverview(
            account=account_view,
            permissions=permissions,
            spot=spot,
            usdm=usdm,
            as_of=utc_now(),
        )
        self._cache.set(tenant_id, self._clock(), overview)
        return overview

    async def _spot_section(
        self,
        pending: Awaitable[SpotAccountSnapshot],
    ) -> OverviewSection[SpotAccountSnapshot]:
        try:
            snapshot = await pending
        except Exception as error:
            return self._error_section(
                self._error_code(error, "binance.spot_unavailable"),
            )
        return OverviewSection(
            status="ok",
            data=snapshot.model_copy(
                update={
                    "balances": [
                        balance for balance in snapshot.balances if balance.total != Decimal(0)
                    ]
                }
            ),
        )

    async def _usdm_section(
        self,
        pending: Awaitable[UsdmAccountSnapshot],
    ) -> OverviewSection[UsdmAccountSnapshot]:
        try:
            snapshot = await pending
        except Exception as error:
            return self._error_section(
                self._error_code(error, "binance.usdm_unavailable"),
            )
        return OverviewSection(
            status="ok",
            data=snapshot.model_copy(
                update={
                    "positions": [
                        position
                        for position in snapshot.positions
                        if position.quantity != Decimal(0)
                    ]
                }
            ),
        )

    @staticmethod
    def _error_code(error: Exception, fallback: str) -> str:
        return error.code if isinstance(error, BinanceConnectorError) else fallback

    @staticmethod
    def _error_section[T](code: str) -> OverviewSection[T]:
        return OverviewSection(
            status="error",
            data=None,
            error=ProblemSummary(code=code, message="Binance data is temporarily unavailable"),
        )

    @staticmethod
    def _account_view(account: TradingAccount) -> BinanceAccountView:
        if account.api_key_fingerprint is None or account.last_permission_check_at is None:
            raise ValueError("Binance account verification metadata is unavailable")
        return BinanceAccountView(
            alias=account.alias,
            api_key_fingerprint=account.api_key_fingerprint,
            connection_status=account.connection_status,
            last_verified_at=account.last_permission_check_at,
        )

    @staticmethod
    def _permissions_view(account: TradingAccount) -> BinancePermissionView:
        return BinancePermissionView(
            can_read=account.can_read,
            can_spot_trade=account.can_spot_trade,
            can_futures_trade=account.can_futures_trade,
            ip_restricted=account.ip_restricted,
            can_withdraw=account.can_withdraw,
            can_internal_transfer=account.can_internal_transfer,
            can_universal_transfer=account.can_universal_transfer,
        )


__all__ = [
    "BinanceOverview",
    "BinanceOverviewCache",
    "BinanceOverviewService",
    "BinancePermissionView",
    "OverviewSection",
    "ProblemSummary",
    "SpotAccountSnapshot",
    "SpotBalance",
    "UsdmAccountSnapshot",
    "UsdmBalance",
    "UsdmPosition",
]

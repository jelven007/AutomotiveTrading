import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic
from typing import Any, Literal

from nautilus_trader.adapters.binance import (
    BinanceLiveDataClientFactory,
    BinanceLiveExecClientFactory,
)
from nautilus_trader.config import TradingNodeConfig
from nautilus_trader.live.node import TradingNode
from nautilus_trader.model.enums import PriceType
from nautilus_trader.model.identifiers import TraderId  # type: ignore[import-not-found]

from trading.binance_runtime.config import build_binance_client_configs
from trading.binance_runtime.overview import (
    SpotAccountSnapshot,
    SpotBalance,
    UsdmAccountSnapshot,
    UsdmBalance,
    UsdmPosition,
)


class NautilusCandidateRuntime:
    def __init__(
        self,
        *,
        api_key: str,
        api_secret: str,
        testnet: bool,
        startup_timeout_seconds: float = 15,
    ) -> None:
        self._startup_timeout_seconds = startup_timeout_seconds
        self._node = self._build_node(api_key, api_secret, testnet)
        self._run_task: asyncio.Task[None] | None = None

    async def validate(self) -> object:
        await self._ensure_started()
        spot, usdm = await asyncio.gather(self.read_spot(), self.read_usdm())
        return {"spot": spot, "usdm": usdm}

    async def read_spot(self) -> SpotAccountSnapshot:
        await self._ensure_started()
        account = self._account("SPOT")
        balances = [
            SpotBalance(
                asset=balance.currency.code,
                free=balance.free.as_decimal(),
                locked=balance.locked.as_decimal(),
                total=balance.total.as_decimal(),
            )
            for balance in account.balances().values()
            if balance.total.as_decimal() != Decimal(0)
        ]
        return SpotAccountSnapshot(
            balances=sorted(balances, key=lambda item: item.asset),
            as_of=self._account_time(account),
        )

    async def read_usdm(self) -> UsdmAccountSnapshot:
        await self._ensure_started()
        account = self._account("USDT_FUTURES")
        balances = [
            UsdmBalance(
                asset=balance.currency.code,
                wallet_balance=balance.total.as_decimal(),
                available_balance=balance.free.as_decimal(),
                unrealized_pnl=Decimal(0),
            )
            for balance in account.balances().values()
            if balance.total.as_decimal() != Decimal(0)
        ]
        positions = [
            self._position_view(account, position)
            for position in self._node.cache.positions_open(account_id=account.id)
            if position.quantity.as_decimal() != Decimal(0)
        ]
        return UsdmAccountSnapshot(
            balances=sorted(balances, key=lambda item: item.asset),
            positions=sorted(positions, key=lambda item: item.symbol),
            as_of=self._account_time(account),
        )

    async def stop(self) -> None:
        if self._run_task is None:
            return
        if self._node.is_running():
            await self._node.stop_async()
        try:
            await asyncio.wait_for(self._run_task, timeout=5)
        except (TimeoutError, asyncio.CancelledError):
            self._run_task.cancel()
        finally:
            self._run_task = None

    async def _ensure_started(self) -> None:
        if self._run_task is None:
            self._node.build()
            self._run_task = asyncio.create_task(self._node.run_async())

        deadline = monotonic() + self._startup_timeout_seconds
        while monotonic() < deadline:
            if self._run_task.done():
                error = self._run_task.exception()
                raise RuntimeError("Nautilus runtime stopped during startup") from error
            if self._has_account("SPOT") and self._has_account("USDT_FUTURES"):
                return
            await asyncio.sleep(0.1)
        raise TimeoutError("Nautilus runtime account state was not ready")

    def _has_account(self, account_type: str) -> bool:
        return any(
            self._matches_account(account, account_type) for account in self._node.cache.accounts()
        )

    def _account(self, account_type: str) -> Any:
        for account in self._node.cache.accounts():
            if self._matches_account(account, account_type):
                return account
        raise RuntimeError(f"Nautilus {account_type} account is not ready")

    def _position_view(self, account: Any, position: Any) -> UsdmPosition:
        instrument_id = position.instrument_id
        mark = self._node.cache.price(instrument_id, PriceType.MARK)
        unrealized = self._node.portfolio.unrealized_pnl(
            instrument_id,
            price=mark,
            account_id=account.id,
        )
        leverage = account.leverage(instrument_id)
        margin_mode: Literal["cross", "isolated"] = (
            "isolated" if instrument_id in account.margins() else "cross"
        )
        return UsdmPosition(
            symbol=str(instrument_id.symbol),
            side=self._position_side(position.side),
            quantity=position.quantity.as_decimal(),
            entry_price=Decimal(str(position.avg_px_open)),
            mark_price=mark.as_decimal() if mark is not None else None,
            unrealized_pnl=unrealized.as_decimal() if unrealized is not None else None,
            leverage=int(leverage) if leverage is not None else None,
            margin_mode=margin_mode,
        )

    @staticmethod
    def _matches_account(account: Any, account_type: str) -> bool:
        return f"-{account_type}-" in str(account.id)

    @staticmethod
    def _position_side(side: Any) -> Literal["long", "short", "flat"]:
        value = getattr(side, "name", str(side)).lower()
        if value == "long":
            return "long"
        if value == "short":
            return "short"
        return "flat"

    @staticmethod
    def _account_time(account: Any) -> datetime:
        timestamp_ns = getattr(account.last_event, "ts_event", 0)
        if timestamp_ns:
            return datetime.fromtimestamp(timestamp_ns / 1_000_000_000, tz=UTC)
        return datetime.now(UTC)

    @staticmethod
    def _build_node(api_key: str, api_secret: str, testnet: bool) -> TradingNode:
        configs = build_binance_client_configs(
            api_key=api_key,
            api_secret=api_secret,
            testnet=testnet,
        )
        node = TradingNode(
            config=TradingNodeConfig(
                trader_id=TraderId("BINANCE-READONLY"),
                data_clients={
                    configs.spot.client_id: configs.spot.data,
                    configs.futures.client_id: configs.futures.data,
                },
                exec_clients={
                    configs.spot.client_id: configs.spot.execution,
                    configs.futures.client_id: configs.futures.execution,
                },
            )
        )
        node.add_data_client_factory(
            configs.spot.client_id,
            BinanceLiveDataClientFactory,
        )
        node.add_data_client_factory(
            configs.futures.client_id,
            BinanceLiveDataClientFactory,
        )
        node.add_exec_client_factory(
            configs.spot.client_id,
            BinanceLiveExecClientFactory,
        )
        node.add_exec_client_factory(
            configs.futures.client_id,
            BinanceLiveExecClientFactory,
        )
        return node


class NautilusRuntimeFactory:
    def __init__(self, *, testnet: bool = False) -> None:
        self._testnet = testnet

    async def __call__(
        self,
        api_key: str,
        api_secret: str,
    ) -> NautilusCandidateRuntime:
        return NautilusCandidateRuntime(
            api_key=api_key,
            api_secret=api_secret,
            testnet=self._testnet,
        )


__all__ = ["NautilusCandidateRuntime", "NautilusRuntimeFactory"]

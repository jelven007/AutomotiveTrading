from dataclasses import dataclass

from nautilus_trader.adapters.binance import (
    BinanceAccountType,
    BinanceDataClientConfig,
    BinanceExecClientConfig,
    BinanceKeyType,
)
from nautilus_trader.adapters.binance.common.enums import BinanceEnvironment
from nautilus_trader.model.identifiers import Venue  # type: ignore[import-not-found]


@dataclass(frozen=True, slots=True)
class BinanceClientConfig:
    client_id: str
    data: BinanceDataClientConfig
    execution: BinanceExecClientConfig | None


@dataclass(frozen=True, slots=True)
class BinanceClientConfigs:
    spot: BinanceClientConfig
    futures: BinanceClientConfig


def build_binance_client_configs(
    *,
    api_key: str | None = None,
    api_secret: str | None = None,
    testnet: bool,
) -> BinanceClientConfigs:
    """构造相互隔离的币安现货与 U 本位客户端配置。"""
    if (api_key is None) != (api_secret is None):
        raise ValueError("api_key and api_secret must be provided together")

    environment = BinanceEnvironment.TESTNET if testnet else BinanceEnvironment.LIVE

    def build_client(client_id: str, account_type: BinanceAccountType) -> BinanceClientConfig:
        venue = Venue(client_id)
        data = BinanceDataClientConfig(
            api_key=api_key,
            api_secret=api_secret,
            key_type=BinanceKeyType.HMAC,
            account_type=account_type,
            environment=environment,
            venue=venue,
        )
        execution = None
        if api_key is not None:
            execution = BinanceExecClientConfig(
                api_key=api_key,
                api_secret=api_secret,
                key_type=BinanceKeyType.HMAC,
                account_type=account_type,
                environment=environment,
                venue=venue,
            )
        return BinanceClientConfig(
            client_id=client_id,
            data=data,
            execution=execution,
        )

    return BinanceClientConfigs(
        spot=build_client("BINANCE_SPOT", BinanceAccountType.SPOT),
        futures=build_client("BINANCE_FUTURES", BinanceAccountType.USDT_FUTURES),
    )

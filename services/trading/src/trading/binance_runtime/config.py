from dataclasses import dataclass
from typing import Literal

from nautilus_trader.adapters.binance import (
    BinanceAccountType,
    BinanceDataClientConfig,
    BinanceExecClientConfig,
    BinanceKeyType,
)
from nautilus_trader.adapters.binance.common.enums import BinanceEnvironment

CredentialType = Literal["hmac", "ed25519"]


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
    credential_type: CredentialType | str = "hmac",
    testnet: bool,
) -> BinanceClientConfigs:
    """构造相互隔离的币安现货与 U 本位客户端配置。"""
    if (api_key is None) != (api_secret is None):
        raise ValueError("api_key and api_secret must be provided together")

    key_types = {
        "hmac": BinanceKeyType.HMAC,
        "ed25519": BinanceKeyType.ED25519,
    }
    try:
        key_type = key_types[credential_type.lower()]
    except KeyError as error:
        raise ValueError(f"unsupported credential type: {credential_type}") from error

    environment = BinanceEnvironment.TESTNET if testnet else BinanceEnvironment.LIVE

    def build_client(client_id: str, account_type: BinanceAccountType) -> BinanceClientConfig:
        data = BinanceDataClientConfig(
            api_key=api_key,
            api_secret=api_secret,
            key_type=key_type,
            account_type=account_type,
            environment=environment,
        )
        execution = None
        if api_key is not None:
            execution = BinanceExecClientConfig(
                api_key=api_key,
                api_secret=api_secret,
                key_type=key_type,
                account_type=account_type,
                environment=environment,
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

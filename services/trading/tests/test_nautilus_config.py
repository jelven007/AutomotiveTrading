import pytest
from nautilus_trader.adapters.binance import BinanceAccountType, BinanceKeyType
from nautilus_trader.adapters.binance.common.enums import BinanceEnvironment
from trading.binance_runtime.config import build_binance_client_configs


def test_builds_distinct_spot_and_futures_clients() -> None:
    configs = build_binance_client_configs(
        api_key="test-api-key",
        api_secret="test-secret",
    )

    assert configs.spot.client_id == "BINANCE_SPOT"
    assert str(configs.spot.data.venue) == "BINANCE_SPOT"
    assert configs.spot.data.account_type is BinanceAccountType.SPOT
    assert configs.spot.execution is not None
    assert configs.spot.execution.account_type is BinanceAccountType.SPOT
    assert configs.spot.execution.key_type is BinanceKeyType.HMAC
    assert configs.futures.client_id == "BINANCE_FUTURES"
    assert str(configs.futures.data.venue) == "BINANCE_FUTURES"
    assert configs.futures.data.account_type is BinanceAccountType.USDT_FUTURES
    assert configs.futures.execution is not None
    assert configs.futures.execution.account_type is BinanceAccountType.USDT_FUTURES
    assert configs.futures.execution.key_type is BinanceKeyType.HMAC
    assert configs.spot.data.environment is BinanceEnvironment.DEMO
    assert configs.futures.data.environment is BinanceEnvironment.DEMO


def test_without_credentials_builds_data_clients_only() -> None:
    configs = build_binance_client_configs()

    assert configs.spot.execution is None
    assert configs.futures.execution is None
    assert configs.spot.data.api_key is None
    assert configs.spot.data.api_secret is None
    assert configs.futures.data.api_key is None
    assert configs.futures.data.api_secret is None


@pytest.mark.parametrize(
    ("api_key", "api_secret"),
    [
        pytest.param("test-api-key", None, id="missing_secret"),
        pytest.param(None, "test-secret", id="missing_api_key"),
    ],
)
def test_rejects_partial_credentials(
    api_key: str | None,
    api_secret: str | None,
) -> None:
    with pytest.raises(ValueError, match="provided together"):
        build_binance_client_configs(
            api_key=api_key,
            api_secret=api_secret,
        )

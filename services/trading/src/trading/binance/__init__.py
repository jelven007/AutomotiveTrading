"""Binance read-only permission probe with lazy public exports."""

__all__ = ["BinancePermissionProbe"]


def __getattr__(name: str) -> object:
    if name in __all__:
        from trading.binance.client import BinancePermissionProbe

        return BinancePermissionProbe
    raise AttributeError(name)

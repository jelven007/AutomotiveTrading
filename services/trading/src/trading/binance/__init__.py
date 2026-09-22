"""Binance Demo account probe with lazy public exports."""

__all__ = ["BinanceDemoAccountProbe"]


def __getattr__(name: str) -> object:
    if name in __all__:
        from trading.binance.client import BinanceDemoAccountProbe

        return BinanceDemoAccountProbe
    raise AttributeError(name)

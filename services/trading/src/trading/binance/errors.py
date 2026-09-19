class BinanceConnectorError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        retry_after_seconds: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retry_after_seconds = retry_after_seconds


class BinanceWriteTimeout(BinanceConnectorError):
    def __init__(self) -> None:
        super().__init__(
            "binance.write_timeout",
            "Binance write result is unknown and must be reconciled",
        )

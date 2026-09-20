from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class ProviderName(StrEnum):
    MOOTDX = "mootdx"


class Dataset(StrEnum):
    QUOTE = "quote"
    BAR = "bar"
    TRANSACTION = "transaction"
    INSTRUMENT = "instrument"
    BLOCK = "block"
    CORPORATE_ACTION = "corporate_action"
    FINANCIAL = "financial"
    F10 = "f10"
    READER_FILE = "reader_file"


@dataclass(frozen=True)
class PriceLevel:
    price: Decimal
    quantity: Decimal


@dataclass(frozen=True)
class QuoteRecord:
    exchange: str
    symbol: str
    source_time: datetime
    collected_at: datetime
    last_price: Decimal
    previous_close: Decimal
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    volume: Decimal
    amount: Decimal
    bids: tuple[PriceLevel, ...] = ()
    asks: tuple[PriceLevel, ...] = ()
    provider: ProviderName | str = ProviderName.MOOTDX
    source_id: str = ""
    payload_hash: str = ""
    quality_reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.source_time.tzinfo is None or self.collected_at.tzinfo is None:
            raise ValueError("quote timestamps must be timezone-aware")

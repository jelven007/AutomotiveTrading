from __future__ import annotations

import hashlib
from collections.abc import Iterable


def _score(symbol: str) -> bytes:
    return hashlib.sha256(symbol.encode()).digest()


def build_quote_shards(
    symbols: Iterable[str],
    *,
    shard_count: int,
) -> tuple[tuple[str, ...], ...]:
    if shard_count <= 0:
        raise ValueError("shard_count must be positive")

    unique_symbols = sorted({symbol.strip() for symbol in symbols if symbol.strip()}, key=_score)
    shards: list[list[str]] = [[] for _ in range(shard_count)]
    for index, symbol in enumerate(unique_symbols):
        shards[index % shard_count].append(symbol)
    return tuple(tuple(sorted(shard)) for shard in shards)

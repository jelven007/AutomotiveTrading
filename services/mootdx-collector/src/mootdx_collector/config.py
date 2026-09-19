from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    core_url: str = "http://instrument-market:8000"
    service_token: str = field(default="", repr=False)
    tushare_token: str = field(default="", repr=False)
    spool_path: Path = Path("/data/collector.sqlite3")
    workers: int = 8
    batch_size: int = 80
    timeout: float = 2.0
    sweep_seconds: float = 2.0
    closed_seconds: float = 300.0
    universe_refresh_seconds: float = 86400.0
    max_pending: int = 10000
    max_spool_bytes: int = 10 * 1024**3
    min_free_bytes: int = 512 * 1024**2
    probe_limit: int = 128
    endpoints: str = ""
    health_host: str = "127.0.0.1"
    health_port: int = 8010

    def __post_init__(self) -> None:
        bounds = {
            "workers": (1, 16),
            "batch_size": (1, 80),
            "timeout": (0.2, 15),
            "sweep_seconds": (0.5, 300),
            "closed_seconds": (10, 86400),
            "universe_refresh_seconds": (3600, 604800),
            "max_pending": (1, 1000000),
            "max_spool_bytes": (1024, 1024**4),
            "min_free_bytes": (0, 1024**4),
            "probe_limit": (1, 128),
            "health_port": (1024, 65535),
        }
        for name, (lower, upper) in bounds.items():
            if not lower <= getattr(self, name) <= upper:
                raise ValueError(f"{name} must be within {lower}..{upper}")
        url = urlsplit(self.core_url)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username:
            raise ValueError("invalid core_url")

    @classmethod
    def from_env(cls) -> Settings:
        values = {}
        defaults = cls()
        for name in cls.__dataclass_fields__:
            value = os.getenv(f"COLLECTOR_{name.upper()}")
            if value is not None:
                values[name] = type(getattr(defaults, name))(value)
        values["service_token"] = os.getenv(
            "MARKET_INGEST_SERVICE_TOKEN",
            values.get("service_token", ""),
        )
        values["tushare_token"] = os.getenv("TUSHARE_TOKEN", values.get("tushare_token", ""))
        return cls(**values)

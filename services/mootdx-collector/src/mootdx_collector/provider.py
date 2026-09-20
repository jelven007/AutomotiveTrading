from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

from mootdx_collector.config import Settings

MARKETS = {"SZSE": 0, "SSE": 1}
FACTORY_LOCK = threading.Lock()


@dataclass(frozen=True)
class Node:
    host: str
    port: int
    latency_ms: int = 0

    @property
    def alias(self) -> str:
        return "tdx-" + hashlib.sha256(f"{self.host}:{self.port}".encode()).hexdigest()[:12]


def discover(settings: Settings) -> list[Node]:
    from mootdx.consts import HQ_HOSTS
    from tdxpy.constants import hq_hosts
    from tdxpy.hq import TdxHq_API

    candidates = (
        [
            Node(host, int(port))
            for host, port in (
                part.strip().rsplit(":", 1) for part in settings.endpoints.split(",")
            )
        ]
        if settings.endpoints
        else [Node(host, port) for _, host, port in hq_hosts + HQ_HOSTS]
    )
    candidates = list(dict.fromkeys(candidates))[: settings.probe_limit]

    def probe(node: Node) -> Node | None:
        api = TdxHq_API(heartbeat=False, auto_retry=False, raise_exception=True)
        started = time.monotonic()
        try:
            if not api.connect(node.host, node.port, time_out=settings.timeout):
                return None
            rows = api.get_security_quotes([(1, "600000"), (0, "000001")]) or []
            seen = {(row.get("market"), row.get("code")) for row in rows}
            if seen != {(1, "600000"), (0, "000001")}:
                return None
            return Node(node.host, node.port, int((time.monotonic() - started) * 1000))
        except Exception:
            return None
        finally:
            # Linux 下连接失败后 shutdown 会再次抛错。清理不能覆盖原来的探测结果。
            with suppress(Exception):
                api.disconnect()

    with ThreadPoolExecutor(max_workers=settings.workers) as executor:
        nodes = [node for node in executor.map(probe, candidates) if node is not None]
    return sorted(nodes, key=lambda node: node.latency_ms)


class Provider:
    """每个线程独占一条连接。所有调用均使用显式 market。禁止代码自动猜市场。"""

    def __init__(self, settings: Settings, nodes: list[Node]) -> None:
        if not nodes:
            raise RuntimeError("no_healthy_tdx_node")
        self.settings = settings
        self.nodes = nodes
        self.local = threading.local()
        self.connections: list[Any] = []
        self.next_node = 0
        self.switches = 0

    def _connect(self):
        from mootdx import config
        from mootdx.logger import logger
        from mootdx.quotes import Quotes

        from mootdx_collector.protocol import read_quotes

        with FACTORY_LOCK:
            node = self.nodes[self.next_node % len(self.nodes)]
            self.next_node += 1
            # 库首次 setup 会触发隐式全量测速。预建配置把测速控制在 discover 内。
            config_path = Path(config.CONF)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            if not config_path.exists():
                config_path.write_text(json.dumps(config.settings))
            logger.disabled = True
            connection = Quotes.factory(
                market="std",
                server=(node.host, node.port),
                timeout=self.settings.timeout,
                bestip=False,
                heartbeat=False,
                auto_retry=False,
                raise_exception=True,
            )
            # 仅替换本实例快照命令。不修改依赖文件或全局 parser。
            connection.client.get_security_quotes = partial(read_quotes, connection.client)
            self.connections.append(connection)
            self.local.connection = connection
            self.local.node = node
        return connection

    def call(self, method: str, *args) -> tuple[Any, str]:
        for attempt in range(2):
            try:
                connection = getattr(self.local, "connection", None) or self._connect()
                result = getattr(connection.client, method)(*args)
                if result is None:
                    raise RuntimeError("empty_protocol_response")
                return result, self.local.node.alias
            except Exception as error:
                connection = getattr(self.local, "connection", None)
                if connection is not None:
                    with suppress(Exception):
                        connection.close()
                    with FACTORY_LOCK:
                        self.connections.remove(connection)
                    self.local.connection = None
                if attempt == 1:
                    raise RuntimeError("tdx_request_failed") from error
                with FACTORY_LOCK:
                    self.switches += 1
        raise RuntimeError("tdx_request_failed")

    def quotes(self, exchange: str, codes: list[str]) -> dict[str, Any]:
        if len(codes) > 80 or not codes:
            raise ValueError("quote batch must contain 1..80 symbols")
        if exchange not in MARKETS:
            raise ValueError("unsupported exchange")
        rows, source_id = self.call(
            "get_security_quotes",
            [(MARKETS[exchange], code) for code in codes],
        )
        return {"rows": rows, "source_id": source_id, "error": None}

    def trade_date(self, exchange: str, code: str) -> str | None:
        if exchange not in MARKETS:
            raise ValueError("unsupported exchange")
        rows, _ = self.call("get_security_bars", 9, MARKETS[exchange], code, 0, 1)
        if not rows:
            return None
        row = rows[-1]

        return date(int(row["year"]), int(row["month"]), int(row["day"])).isoformat()

    def daily_bars(self, exchange: str, code: str, count: int = 800) -> dict[str, Any]:
        self._validate_history_request(exchange, code)
        if not 1 <= count <= 800:
            raise ValueError("bar count must be within 1..800")
        rows, source_id = self.call(
            "get_security_bars",
            9,
            MARKETS[exchange],
            code,
            0,
            count,
        )
        return {"rows": rows, "source_id": source_id}

    def minute_history(self, exchange: str, code: str, trade_date: str) -> dict[str, Any]:
        self._validate_history_request(exchange, code)
        encoded_date = int(date.fromisoformat(trade_date).strftime("%Y%m%d"))
        rows, source_id = self.call(
            "get_history_minute_time_data",
            MARKETS[exchange],
            code,
            encoded_date,
        )
        return {"rows": rows, "source_id": source_id}

    def transaction_page(
        self,
        exchange: str,
        code: str,
        trade_date: str,
        start: int,
        count: int = 800,
    ) -> dict[str, Any]:
        self._validate_history_request(exchange, code)
        if not 0 <= start <= 65535:
            raise ValueError("transaction start must be within 0..65535")
        if not 1 <= count <= 800:
            raise ValueError("transaction count must be within 1..800")
        encoded_date = int(date.fromisoformat(trade_date).strftime("%Y%m%d"))
        rows, source_id = self.call(
            "get_history_transaction_data",
            MARKETS[exchange],
            code,
            start,
            count,
            encoded_date,
        )
        return {"rows": rows, "source_id": source_id}

    @staticmethod
    def _validate_history_request(exchange: str, code: str) -> None:
        if exchange not in MARKETS:
            raise ValueError("unsupported exchange")
        if len(code) != 6 or not code.isascii() or not code.isdigit():
            raise ValueError("invalid symbol")

    def close(self) -> None:
        for connection in self.connections:
            with suppress(Exception):
                connection.close()
        self.connections.clear()

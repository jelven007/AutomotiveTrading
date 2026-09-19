from __future__ import annotations

import gzip
import json
import shutil
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid4


class Spool:
    """原始响应与发送队列共用一次 SQLite 事务。确认后仍保留原始压缩正文。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=15, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        self.db.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS batches (
                id TEXT PRIMARY KEY, route TEXT NOT NULL, body BLOB NOT NULL,
                created REAL NOT NULL, acked INTEGER NOT NULL DEFAULT 0,
                attempts INTEGER NOT NULL DEFAULT 0, retry_at REAL NOT NULL DEFAULT 0,
                error TEXT, response TEXT
            );
            CREATE INDEX IF NOT EXISTS pending ON batches(acked, retry_at, created);
            CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        """)

    def close(self) -> None:
        with self.lock:
            self.db.close()

    def put(
        self,
        route: str,
        body: dict[str, Any],
        *,
        checkpoint: tuple[str, Any] | None = None,
    ) -> str:
        batch_id = body.get("batch_id") or str(uuid4())
        encoded = gzip.compress(json.dumps(body, ensure_ascii=False, allow_nan=False).encode())
        with self.lock, self.db:
            self.db.execute(
                "INSERT INTO batches(id,route,body,created,acked) VALUES (?,?,?,?,?)",
                (batch_id, route, encoded, time.time(), int(not route)),
            )
            if checkpoint:
                self._set(*checkpoint)
        return batch_id

    def due(self) -> dict[str, Any] | None:
        with self.lock:
            row = self.db.execute(
                "SELECT * FROM batches WHERE acked=0 AND retry_at<=? ORDER BY created LIMIT 1",
                (time.time(),),
            ).fetchone()
            return {**dict(row), "body": json.loads(gzip.decompress(row["body"]))} if row else None

    def ack(self, batch_id: str, response: dict[str, Any]) -> None:
        with self.lock, self.db:
            self.db.execute(
                "UPDATE batches SET acked=1,error=NULL,response=? WHERE id=?",
                (json.dumps(response), batch_id),
            )

    def retry(self, batch_id: str, delay: float, reason: str) -> None:
        with self.lock, self.db:
            self.db.execute(
                "UPDATE batches SET attempts=attempts+1,retry_at=?,error=? WHERE id=?",
                (time.time() + delay, reason, batch_id),
            )

    def _set(self, key: str, value: Any) -> None:
        self.db.execute(
            "INSERT INTO state VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value, ensure_ascii=False)),
        )

    def set(self, key: str, value: Any) -> None:
        with self.lock, self.db:
            self._set(key, value)

    def get(self, key: str) -> Any:
        with self.lock:
            row = self.db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else None

    def stats(self) -> dict[str, Any]:
        with self.lock:
            row = self.db.execute("""
                SELECT count(*) AS batches, coalesce(sum(acked=0),0) AS pending,
                       coalesce(sum(acked=1 AND route!=''),0) AS delivered,
                       coalesce(sum(length(body)),0) AS compressed_bytes
                FROM batches
            """).fetchone()
            error = self.db.execute(
                "SELECT error FROM batches WHERE acked=0 AND error IS NOT NULL "
                "ORDER BY created DESC LIMIT 1"
            ).fetchone()
            accepted = self.db.execute(
                "SELECT coalesce(sum(json_extract(response,'$.accepted')),0) FROM batches "
                "WHERE acked=1 AND route='/internal/v1/market/quotes'"
            ).fetchone()[0]
            size = sum(p.stat().st_size for p in self.path.parent.glob(self.path.name + "*"))
            return {
                **dict(row),
                "file_bytes": size,
                "delivered_quotes": accepted,
                "free_bytes": shutil.disk_usage(self.path.parent).free,
                "last_delivery_error": error[0] if error else None,
            }

    def has_capacity(self, *, max_pending: int, max_bytes: int, min_free: int) -> bool:
        stats = self.stats()
        return (
            stats["pending"] < max_pending
            and stats["file_bytes"] < max_bytes
            and stats["free_bytes"] > min_free
        )

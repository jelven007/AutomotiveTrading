from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Callable
from typing import Any, cast

from sqlalchemy import Column, Engine, MetaData, String, Table, Text, create_engine, select
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from instrument_market.errors import ServiceError

metadata = MetaData()
receipts = Table(
    "market_ingest_receipts",
    metadata,
    Column("batch_id", String(80), primary_key=True),
    Column("content_hash", String(64), nullable=False),
    Column("result_json", Text().with_variant(LONGTEXT(), "mysql"), nullable=True),
)


class ReceiptStore:
    """关系库确认凭证。数据库行锁串行化同一批次。跨存储失败允许逻辑重放。"""

    def __init__(self, engine: Engine | None = None) -> None:
        self.engine = engine or create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.lock = threading.Lock()
        if engine is None:
            metadata.create_all(self.engine)

    def apply(
        self,
        batch_id: str,
        body: dict[str, Any],
        operation: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        encoded = json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        # 本地锁兼容 SQLite。生产多进程由 MySQL SELECT FOR UPDATE 保护。
        with self.lock:
            try:
                with self.engine.begin() as conn:
                    conn.execute(receipts.insert().values(batch_id=batch_id, content_hash=digest))
            except IntegrityError:
                pass
            with self.engine.begin() as conn:
                row = (
                    conn.execute(
                        select(receipts).where(receipts.c.batch_id == batch_id).with_for_update()
                    )
                    .mappings()
                    .one()
                )
                if row["content_hash"] != digest:
                    raise ServiceError(
                        code="market.batch_conflict",
                        message="Batch content conflicts",
                        status_code=409,
                    )
                if row["result_json"] is not None:
                    return cast(dict[str, Any], json.loads(row["result_json"]))
                result = operation()
                conn.execute(
                    receipts.update()
                    .where(receipts.c.batch_id == batch_id)
                    .values(result_json=json.dumps(result, ensure_ascii=False))
                )
                return result

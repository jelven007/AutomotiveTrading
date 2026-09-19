import gzip
import json

import pytest
from mootdx_collector.spool import Spool


def test_spool_restart_keeps_raw_retry_id_and_checkpoint(tmp_path):
    path = tmp_path / "spool.db"
    spool = Spool(path)
    body = {"batch_id": "batch-1", "quotes": [{"code": "600000", "unknown_field": 42}]}
    spool.put("/quotes", body, checkpoint=("cursor", {"offset": 80}))
    spool.retry("batch-1", 0, "ConnectError")
    spool.close()
    recovered = Spool(path)
    assert recovered.due()["body"] == body
    assert recovered.due()["attempts"] == 1
    assert recovered.get("cursor") == {"offset": 80}
    recovered.ack("batch-1", {"accepted": 1})
    assert recovered.due() is None
    raw = recovered.db.execute("SELECT body FROM batches WHERE id='batch-1'").fetchone()[0]
    assert json.loads(gzip.decompress(raw)) == body
    assert recovered.stats()["pending"] == 0
    recovered.close()


def test_spool_checkpoint_rolls_back_with_failed_insert(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    spool.put("/quotes", {"batch_id": "same"}, checkpoint=("cursor", 1))
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError):
        spool.put("/quotes", {"batch_id": "same"}, checkpoint=("cursor", 2))
    assert spool.get("cursor") == 1
    assert spool.has_capacity(max_pending=1, max_bytes=10**9, min_free=0) is False
    assert spool.has_capacity(max_pending=100, max_bytes=1, min_free=0) is False
    assert spool.has_capacity(max_pending=100, max_bytes=10**9, min_free=10**20) is False
    spool.close()

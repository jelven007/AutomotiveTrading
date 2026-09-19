from datetime import UTC, datetime

import pytest
from mootdx_collector.collector import Collector, active_session, response_coverage
from mootdx_collector.config import Settings
from mootdx_collector.spool import Spool


@pytest.mark.parametrize(
    "at,active",
    [
        ("2026-09-18T01:30:00+00:00", True),
        ("2026-09-18T04:00:00+00:00", False),
        ("2026-09-20T01:30:00+00:00", False),
        ("2026-09-18T06:00:00+00:00", True),
    ],
)
def test_session_schedule(at, active):
    assert active_session(datetime.fromisoformat(at)) is active


def test_coverage_excludes_wrong_market_duplicates_and_unexpected():
    result = response_coverage(
        "SSE",
        ["600000", "600001"],
        [
            {"code": "600000", "market": 1},
            {"code": "600000", "market": 1},
            {"code": "600001", "market": 0},
            {"code": "600839", "market": 1},
        ],
    )
    assert result["received"] == 1
    assert result["missing"] == ["600001"]
    assert result["duplicates"] == ["600000"]
    assert len(result["unexpected"]) == 2


def test_collector_persists_partial_response_and_round_checkpoint(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    instruments = [
        {"exchange": "SSE", "code": code, "volunit": 100, "decimal_point": 2}
        for code in ("600000", "600001")
    ]
    spool.set(
        "universe",
        {
            "observed_at": datetime.now(UTC).isoformat(),
            "verification": "unverified",
            "markets": {
                "SSE": {"instruments": instruments, "complete": True, "reason": None},
                "BSE": {"instruments": [], "complete": False, "reason": "bse_protocol_unsupported"},
            },
        },
    )

    class Provider:
        switches = 0

        def trade_date(self, exchange, code):
            return "2026-09-18"

        def quotes(self, exchange, codes):
            return {
                "rows": [
                    {"market": 1, "code": "600000", "price": 10, "servertime": "15:00:00.001"}
                ],
                "source_id": "node-test",
                "error": None,
            }

        def close(self):
            pass

    collector = Collector(Settings(min_free_bytes=0), spool, Provider())
    report = collector.once()
    assert report["received"] == 1
    assert report["expected"] == 2
    assert report["markets"]["SSE"]["missing"] == ["600001"]
    assert report["status"] == "partial"
    assert spool.get("active_round") is None
    body = spool.due()["body"]
    assert body["trade_date"] == "2026-09-18"
    assert body["metadata"]["trade_date_basis"] == "daily_bar_inferred"
    assert body["metadata"]["instruments"]["600000"]["volunit"] == 100
    assert spool.get("latest_round") == report
    collector.close()
    spool.close()

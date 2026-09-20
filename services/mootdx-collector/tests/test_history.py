from datetime import UTC, datetime

from mootdx_collector.config import Settings
from mootdx_collector.history import HistoryCollector, minute_datetimes
from mootdx_collector.spool import Spool


def universe() -> dict:
    instruments = [
        {
            "exchange": exchange,
            "code": code,
            "volunit": 100,
            "decimal_point": 2,
        }
        for exchange, code in (("SSE", "600000"), ("SZSE", "000001"))
    ]
    return {
        "observed_at": "2026-09-20T00:00:00+00:00",
        "source": "mootdx",
        "scope": "sse_szse_candidate",
        "markets": {},
        "instruments": instruments,
    }


class HistoryProvider:
    def __init__(self, *, full_pages: int = 0) -> None:
        self.full_pages = full_pages
        self.transaction_starts: list[int] = []

    def daily_bars(self, exchange, code, count):
        return {
            "rows": [
                {
                    "open": 9.05,
                    "close": 9.07,
                    "high": 9.15,
                    "low": 9,
                    "vol": 517593,
                    "amount": 469969408,
                    "datetime": "2026-09-18 15:00",
                }
            ],
            "source_id": "node-test",
        }

    def minute_history(self, exchange, code, trade_date):
        return {
            "rows": [{"price": 9.02, "vol": 13604} for _ in range(240)],
            "source_id": "node-test",
        }

    def transaction_page(self, exchange, code, trade_date, start, count):
        self.transaction_starts.append(start)
        size = count if len(self.transaction_starts) <= self.full_pages else 2
        return {
            "rows": [
                {"time": "09:31", "price": 9.02, "vol": 3, "buyorsell": 0}
                for _ in range(size)
            ],
            "source_id": "node-test",
        }

    def close(self):
        pass


def test_minute_datetimes_map_the_two_trading_sessions() -> None:
    values = minute_datetimes("2026-09-18", 240)

    assert values[0].isoformat() == "2026-09-18T01:31:00+00:00"
    assert values[119].isoformat() == "2026-09-18T03:30:00+00:00"
    assert values[120].isoformat() == "2026-09-18T05:01:00+00:00"
    assert values[-1].isoformat() == "2026-09-18T07:00:00+00:00"


def test_history_collector_persists_three_datasets_and_restart_cursor(tmp_path) -> None:
    path = tmp_path / "spool.db"
    spool = Spool(path)
    spool.set("universe", universe())
    spool.set("latest_round", {"source_dates": {"SSE": "2026-09-18", "SZSE": "2026-09-18"}})
    provider = HistoryProvider()
    settings = Settings(
        min_free_bytes=0,
        history_request_interval=0,
        history_transaction_page_size=3,
    )

    report = HistoryCollector(settings, spool, provider).collect_one()

    assert report["exchange"] == "SSE"
    assert report["symbol"] == "600000"
    assert report["datasets"]["minute"]["received"] == 240
    assert report["datasets"]["transaction"]["complete"] is True
    assert provider.transaction_starts == [0]
    routes = [
        row[0]
        for row in spool.db.execute(
            "SELECT route FROM batches WHERE route != '' ORDER BY created"
        ).fetchall()
    ]
    assert routes == [
        "/internal/v1/market/bars",
        "/internal/v1/market/minutes",
        "/internal/v1/market/transactions",
        "/internal/v1/market/reports",
    ]
    spool.close()

    recovered = Spool(path)
    second = HistoryCollector(settings, recovered, HistoryProvider()).collect_one()
    assert second["exchange"] == "SZSE"
    assert second["symbol"] == "000001"
    recovered.close()


def test_transaction_page_limit_marks_coverage_partial(tmp_path) -> None:
    spool = Spool(tmp_path / "spool.db")
    spool.set("universe", universe())
    spool.set("latest_round", {"source_dates": {"SSE": "2026-09-18"}})
    provider = HistoryProvider(full_pages=2)
    settings = Settings(
        min_free_bytes=0,
        history_request_interval=0,
        history_transaction_page_size=2,
        history_transaction_max_pages=2,
    )

    report = HistoryCollector(settings, spool, provider).collect_one()

    assert provider.transaction_starts == [0, 2]
    assert report["status"] == "partial"
    assert report["datasets"]["transaction"] == {
        "received": 4,
        "pages": 2,
        "complete": False,
        "reason": "page_limit_reached",
    }
    transaction = spool.db.execute(
        "SELECT body FROM batches WHERE route='/internal/v1/market/transactions'"
    ).fetchone()
    assert transaction is not None
    spool.close()


def test_history_collector_pauses_before_network_when_spool_is_full(tmp_path) -> None:
    spool = Spool(tmp_path / "spool.db")
    spool.set("universe", universe())
    spool.set("latest_round", {"source_dates": {"SSE": "2026-09-18"}})
    spool.put("/pending", {"batch_id": "existing"})

    result = HistoryCollector(
        Settings(max_pending=1, min_free_bytes=0),
        spool,
        HistoryProvider(),
        clock=lambda: datetime(2026, 9, 20, tzinfo=UTC),
    ).collect_one()

    assert result["status"] == "paused_capacity"
    assert spool.get("history_cursor") is None
    spool.close()

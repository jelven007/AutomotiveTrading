import pytest
from mootdx_collector.spool import Spool
from mootdx_collector.universe import enumerate_market, is_candidate, sync_universe


@pytest.mark.parametrize(
    "exchange,code,expected",
    [
        ("SZSE", "302132", True),
        ("SZSE", "000001", True),
        ("SSE", "689009", True),
        ("SSE", "600000", True),
        ("BSE", "920002", False),
        ("SZSE", "159001", False),
        ("SSE", "000001", False),
        ("SSE", "\uff16\uff10\uff10\uff10\uff10\uff10", False),
    ],
)
def test_candidate_classification(exchange, code, expected):
    assert is_candidate(exchange, code) is expected


class Pages:
    def __init__(self, *, bad=None):
        self.offsets = []
        self.bad = bad

    def call(self, method, market, offset=None):
        if method == "get_security_count":
            return 2, "node-test"
        self.offsets.append(offset)
        if self.bad == "empty" and offset == 1:
            return [], "node-test"
        code = "000001" if offset == 0 or self.bad == "repeat" else "302132"
        return [{"code": code, "name": code, "volunit": 100, "decimal_point": 2}], "node-test"


def test_security_pages_advance_by_actual_response_length(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    provider = Pages()
    result = enumerate_market(provider, spool, "SZSE")
    assert provider.offsets == [0, 1]
    assert result["complete"] is True
    assert [row["code"] for row in result["instruments"]] == ["000001", "302132"]
    assert spool.stats()["batches"] == 2
    spool.close()


@pytest.mark.parametrize(
    "bad,reason",
    [
        ("empty", "empty_security_page"),
        ("repeat", "repeated_security_page"),
    ],
)
def test_security_pages_reject_incomplete_or_repeated_page(tmp_path, bad, reason):
    spool = Spool(tmp_path / "spool.db")
    with pytest.raises(ValueError, match=reason):
        enumerate_market(Pages(bad=bad), spool, "SZSE")
    assert spool.stats()["batches"] == 2
    spool.close()


def test_failed_refresh_preserves_cached_universe_and_gap(tmp_path):
    spool = Spool(tmp_path / "spool.db")
    spool.set(
        "universe",
        {
            "markets": {
                "SZSE": {
                    "instruments": [{"exchange": "SZSE", "code": "000001"}],
                    "last_success_at": "2026-09-18T00:00:00+00:00",
                }
            },
        },
    )
    result = sync_universe(Pages(bad="empty"), spool)
    assert result["markets"]["SZSE"]["cached"] is True
    assert result["markets"]["SZSE"]["complete"] is False
    assert result["markets"]["SZSE"]["instruments"][0]["code"] == "000001"
    assert set(result["markets"]) == {"SSE", "SZSE"}
    assert result["source"] == "mootdx"
    assert result["scope"] == "sse_szse_candidate"
    assert spool.get("universe") == result
    spool.close()

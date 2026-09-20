import struct
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from mootdx_collector.config import Settings
from mootdx_collector.provider import Node, Provider, discover


@pytest.mark.parametrize(
    "exchange,market,code",
    [
        ("SSE", 1, "600000"),
        ("SZSE", 0, "000001"),
    ],
)
def test_quotes_use_explicit_market(exchange, market, code):
    calls = []
    api = SimpleNamespace(
        get_security_quotes=lambda pairs: calls.append(pairs) or [{"code": code, "market": market}],
    )
    node = Node("127.0.0.1", 7709)
    provider = Provider(Settings(), [node])
    provider.local.connection = SimpleNamespace(client=api)
    provider.local.node = node
    result = provider.quotes(exchange, [code])
    assert calls == [[(market, code)]]
    assert result["source_id"] == node.alias
    assert result["rows"] == [{"code": code, "market": market}]


def test_quotes_reject_out_of_scope_exchange():
    provider = Provider(Settings(), [Node("127.0.0.1", 7709)])
    with pytest.raises(ValueError, match="unsupported exchange"):
        provider.quotes("BSE", ["920002"])
    with pytest.raises(ValueError, match=r"1\.\.80"):
        provider.quotes("SSE", ["600000"] * 81)


def test_provider_constructs_library_wrapper(monkeypatch, tmp_path):
    from mootdx import config
    from mootdx.quotes import Quotes, StdQuotes
    from tdxpy.hq import TdxHq_API
    from tdxpy.parser.std.get_security_quotes import GetSecurityQuotesCmd

    api = TdxHq_API()
    monkeypatch.setattr(
        GetSecurityQuotesCmd, "call_api", lambda self: [{"market": 1, "code": "600000"}]
    )
    connection = Mock(spec=StdQuotes)
    connection.client = api
    factory = Mock(return_value=connection)
    monkeypatch.setattr(Quotes, "factory", factory)
    monkeypatch.setattr(config, "CONF", str(tmp_path / "config.json"))
    provider = Provider(Settings(), [Node("127.0.0.1", 7709)])
    assert provider.quotes("SSE", ["600000"])["rows"] == [{"market": 1, "code": "600000"}]
    assert factory.call_args.kwargs["auto_retry"] is False
    assert factory.call_args.kwargs["server"] == ("127.0.0.1", 7709)
    provider.close()
    connection.close.assert_called_once()


def quote_body(raw_time: int) -> bytes:
    # 协议首字节保存 6 位。后续字节保存 7 位。时间以外均取零以隔离解析边界。
    encoded = [raw_time & 0x3F]
    remaining = raw_time >> 6
    while remaining:
        encoded[-1] |= 0x80
        encoded.append(remaining & 0x7F)
        remaining >>= 7
    return (
        struct.pack("<B6sH", 0, b"302132", 0)
        + bytes(5)
        + bytes(encoded)
        + bytes(3 + 4 + 4 + 20 + 2 + 4 + 4)
    )


@pytest.mark.parametrize(
    "raw_time,expected",
    [(15294977, "15:29:29.862"), (0, "0"), (1, "0"), (999, "0"), (99999999, "0")],
)
def test_quotes_preserve_rows_with_unknown_source_time(monkeypatch, tmp_path, raw_time, expected):
    from mootdx import config
    from mootdx.quotes import Quotes, StdQuotes
    from tdxpy.hq import TdxHq_API
    from tdxpy.parser.std.get_security_quotes import GetSecurityQuotesCmd

    body = struct.pack("<HH", 0, 2) + quote_body(raw_time) + quote_body(15294977)
    monkeypatch.setattr(GetSecurityQuotesCmd, "call_api", lambda self: self.parseResponse(body))
    connection = Mock(spec=StdQuotes)
    connection.client = TdxHq_API(heartbeat=False, auto_retry=False, raise_exception=True)
    monkeypatch.setattr(Quotes, "factory", Mock(return_value=connection))
    monkeypatch.setattr(config, "CONF", str(tmp_path / "config.json"))
    provider = Provider(Settings(), [Node("127.0.0.1", 7709)])
    try:
        result = provider.quotes("SZSE", ["302132"])
        assert len(result["rows"]) == 2
        assert result["rows"][0]["reversed_bytes0"] == raw_time
        assert result["rows"][0]["servertime"] == expected
        assert result["rows"][1]["servertime"] == "15:29:29.862"
    finally:
        provider.close()


def test_discover_rejects_tcp_only_node_and_closes(monkeypatch):
    from tdxpy import hq

    closed = []

    class API:
        def __init__(self, **kwargs):
            self.port = None

        def connect(self, host, port, **kwargs):
            self.port = port
            return True

        def get_security_quotes(self, pairs):
            return [{"market": m, "code": c} for m, c in pairs] if self.port == 7709 else []

        def disconnect(self):
            closed.append(self.port)

    monkeypatch.setattr(hq, "TdxHq_API", API)
    nodes = discover(Settings(endpoints="127.0.0.1:7709,127.0.0.1:7710"))
    assert [node.port for node in nodes] == [7709]
    assert sorted(closed) == [7709, 7710]

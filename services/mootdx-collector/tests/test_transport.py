import json

import httpx
import pytest
from mootdx_collector.config import Settings
from mootdx_collector.spool import Spool
from mootdx_collector.transport import Sender


@pytest.mark.parametrize(
    "mode", ["success", "disconnect", "unauthorized", "wrong_count", "wrong_id"]
)
def test_sender_requires_matching_ack_and_retains_failures(tmp_path, mode):
    spool = Spool(tmp_path / "spool.db")
    batch = {"batch_id": "batch-1", "quotes": [{"code": "600000"}, {"code": "600001"}]}
    spool.put("/internal/v1/market/quotes", batch)
    requests = []

    def receive(request):
        requests.append(json.loads(request.content))
        assert request.headers["X-Service-Token"] == "secret-test"
        if mode == "disconnect":
            raise httpx.ConnectError("offline", request=request)
        if mode == "unauthorized":
            return httpx.Response(401)
        return httpx.Response(
            202,
            json={
                "batch_id": "different" if mode == "wrong_id" else "batch-1",
                "received": 2,
                "accepted": 0 if mode == "wrong_count" else 1,
                "rejected": 1,
            },
        )

    sender = Sender(
        Settings(service_token="secret-test"), spool, transport=httpx.MockTransport(receive)
    )
    assert sender.send_one() is (mode == "success")
    assert requests == [batch]
    assert spool.stats()["pending"] == (0 if mode == "success" else 1)
    if mode != "success":
        assert spool.due() is None
        assert "secret-test" not in str(spool.stats())
        assert sender.delay == (300 if mode == "unauthorized" else 2)
        # 退避到期后的重试仍携带同一批次。不会生成新 ID。
        spool.retry("batch-1", 0, "test_clock")
        assert spool.due()["body"] == batch
    sender.close()
    spool.close()

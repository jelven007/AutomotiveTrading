from __future__ import annotations

import httpx

from mootdx_collector.config import Settings
from mootdx_collector.spool import Spool


class Sender:
    def __init__(self, settings: Settings, spool: Spool, *, transport=None) -> None:
        self.spool = spool
        self.http = httpx.Client(
            base_url=settings.core_url,
            timeout=15,
            headers={"X-Service-Token": settings.service_token},
            transport=transport,
            trust_env=False,
        )
        self.delay = 0.5

    def close(self) -> None:
        self.http.close()

    def send_one(self) -> bool:
        item = self.spool.due()
        self.delay = 0.5
        if item is None:
            return False
        try:
            response = self.http.post(item["route"], json=item["body"])
            response.raise_for_status()
            result = response.json()
            if not isinstance(result, dict) or result.get("batch_id") != item["id"]:
                raise ValueError("ack_batch_mismatch")
            if item["route"].endswith("/quotes"):
                count = len(item["body"]["quotes"])
                if (
                    result.get("received") != count
                    or type(result.get("accepted")) is not int
                    or type(result.get("rejected")) is not int
                    or result["accepted"] < 0
                    or result["rejected"] < 0
                    or result["accepted"] + result["rejected"] != count
                ):
                    raise ValueError("ack_count_mismatch")
            elif result.get("accepted") != 1:
                raise ValueError("ack_count_mismatch")
            self.spool.ack(item["id"], result)
            return True
        except (httpx.HTTPError, ValueError) as error:
            # 只保存错误类别/状态。避免请求头、Token 或完整响应进入状态接口。
            status = (
                error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
            )
            self.delay = (
                300
                if status is not None and 400 <= status < 500
                else min(60, 2 ** min(item["attempts"] + 1, 6))
            )
            reason = f"http_{status}" if status else type(error).__name__
            self.spool.retry(item["id"], self.delay, reason)
            return False

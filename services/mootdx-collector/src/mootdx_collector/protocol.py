from __future__ import annotations

from datetime import time

from tdxpy.parser.std.get_security_quotes import GetSecurityQuotesCmd


class SafeQuotesCommand(GetSecurityQuotesCmd):
    @staticmethod
    def _format_time(time_stamp: str) -> str:
        # 上游偶尔返回短整数。只降级派生时间。原始 reversed_bytes0 仍由父类保留。
        try:
            formatted = GetSecurityQuotesCmd._format_time(time_stamp)
            if len(formatted) < 8:
                return "0"
            # 九点时段上游省略小时的前导零。ISO 时间解析需要补齐。
            formatted = formatted.zfill(12)
            time.fromisoformat(formatted)
            return formatted
        except (ValueError, TypeError):
            return "0"


def read_quotes(client, pairs):
    command = SafeQuotesCommand(client.client, lock=client.lock)
    command.setParams(pairs)
    return command.call_api()

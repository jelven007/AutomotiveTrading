# Instrument Market Service

个人内部 A 股证券主数据与行情服务。

## 职责

- 对接 mootdx `Quotes`、`Reader`、`Affair`。
- 使用 Tushare 补充主数据并执行交叉校验。
- 将控制面状态写入 MySQL。
- 将快照、K 线、分笔和指标写入 ClickHouse。
- 将原始响应和文件归档到 MinIO。
- 将最新行情投影到 Redis。

`mootdx 0.11.7` 固定依赖 `httpx < 0.26`，与平台统一的 `httpx 0.28`
不兼容。生产部署必须将 mootdx 放在隔离采集 Sidecar 中，核心服务通过
内部鉴权接口或 Kafka 接收原始数据，禁止为兼容 mootdx 降级全仓依赖。

当前已接入独立 [mootdx Sidecar](../mootdx-collector/README.md)，由内部 HTTP 接收
原始快照和证券/覆盖报告。MySQL 保存批次确认凭证，ClickHouse 保存原始行、
标准行、源时间依据和质量原因；重试内容冲突返回 409，坏行隔离并保留原始内容。
Kafka 消费者、MinIO 长期归档和 Redis 投影仍待后续实现。

## 验证

```bash
uv run pytest services/instrument-market/tests -v
uv run ruff check services/instrument-market
uv run mypy services/instrument-market/src
```

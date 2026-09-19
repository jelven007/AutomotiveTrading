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

当前里程碑已完成服务骨架、核心标准化规则、ClickHouse DDL 与容器配置。
真实 Provider 采集和 Kafka 消费者按实施计划后续任务继续实现。

## 验证

```bash
uv run pytest services/instrument-market/tests -v
uv run ruff check services/instrument-market
uv run mypy services/instrument-market/src
```

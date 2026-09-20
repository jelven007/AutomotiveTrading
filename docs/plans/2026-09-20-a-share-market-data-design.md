# A 股 mootdx 全量数据与前端分析设计

<!-- markdownlint-disable MD013 -->

> 文档编号：QT-DES-CNMD-001
>
> 状态：Review
>
> 版本：0.3
>
> 日期：2026-09-20
>
> 需求基线：`docs/requirements/a-share-market-data-requirements.md`

## 1. 设计结论

新增 `instrument-market` 逻辑模块，核心服务负责证券主数据、内部一致性校验、
标准化、质量判断、查询和 WebSocket 推送。mootdx 采集运行在独立 Sidecar，
通过内部鉴权接口或 Kafka 将原始数据交给核心服务。

2026-09-20 确认的数据范围仅为上交所（SSE）和深交所（SZSE）A 股。
本文“全市场”均指沪深；北交所不进入采集、补齐、查询展示、覆盖统计和验收范围。

隔离 Sidecar 的原因是 mootdx 0.11.7 固定依赖 `httpx < 0.26`，与平台统一的
`httpx 0.28` 无法在同一 uv workspace 解析。不得为兼容 mootdx 降级其他服务。

采用四类存储：

- MySQL：证券主数据、采集任务、游标、数据质量事件和 F10 索引。
- ClickHouse：快照、分笔、K 线、财务指标及历史版本。
- MinIO：不可变原始响应、TDX 本地文件、财务 ZIP/DAT、F10 原文和 Parquet。
- Redis：最新行情、短期序列号和 WebSocket 扇出状态。

Kafka/Redpanda 作为采集与落库之间的持久缓冲，不作为最终数据仓库。

## 2. 方案比较

| 方案 | 优点 | 问题 | 结论 |
| --- | --- | --- | --- |
| 全部写 MySQL | 部署简单 | 高频写入、压缩和时序扫描能力不足 | 不采用 |
| 全部写 ClickHouse | 行情查询快 | 配置事务、原始文件和正文管理不合适 | 不采用 |
| MySQL + ClickHouse + MinIO + Redis | 职责清晰、可回放、查询稳定 | 多一个 ClickHouse 运维组件 | 推荐 |

个人内部系统仍保留现有微服务边界。除依赖隔离所必需的 mootdx Sidecar 外，
不继续拆分质量、查询等独立服务，避免增加部署和故障面。

## 3. 总体架构

```text
mootdx Quotes ─┐
mootdx Reader ─┼─> mootdx collector Sidecar
mootdx Affair ─┘          │ 内部鉴权 API / Kafka
                          v
                 instrument-market core
                          ├─> local spool/WAL
                          └─> Kafka/Redpanda
                                  │
                    ┌─────────────┼──────────────┐
                    │             │              │
                Raw writer    Normalizer    Quality evaluator
                    │             │              │
                  MinIO       ClickHouse       MySQL
                                  │
                               Redis latest
                                  │
                     REST + WebSocket API
                                  │
                        React 数据工作台
```

### 3.1 关键原则

1. 先保存后加工：采集结果先进入本地 WAL 和 Kafka，再异步标准化。
2. 原始不可变：原始记录只追加，标准化规则升级后可重新回放。
3. 至少一次投递：允许重复消息，通过业务幂等键消除重复。
4. 来源透明：查询结果携带来源、源时间、采集时间、质量和覆盖状态。
5. 缺失显式：沪深范围内 mootdx 不支持或无法完整获取的数据标记为缺口。

## 4. Provider 与采集模块

目录建议：

```text
services/instrument-market/src/instrument_market/
├── clients/
│   ├── base.py
│   ├── mootdx_collector.py
├── collectors/
│   ├── quote.py
│   ├── transaction.py
│   ├── bar.py
│   ├── reference.py
│   ├── f10.py
│   └── financial.py
├── pipeline/
│   ├── envelope.py
│   ├── normalize.py
│   ├── quality.py
│   ├── deduplicate.py
│   └── checkpoint.py
├── storage/
│   ├── mysql.py
│   ├── clickhouse.py
│   ├── minio.py
│   └── redis.py
└── api/
    ├── quotes.py
    ├── instruments.py
    ├── history.py
    ├── operations.py
    └── websocket.py
```

Sidecar 使用独立 Python 环境和镜像：

```text
services/mootdx-collector/
├── providers/
│   ├── quotes.py
│   ├── reader.py
│   └── affair.py
├── scheduler/
└── transport/
```

### 4.1 能力矩阵

| 数据类型 | mootdx 接口 | 采集方式 | 完整性 |
| --- | --- | --- | --- |
| 实时快照/五档 | `Quotes.quotes` | 全市场分片循环 | 尽力保证 |
| K 线 | `bars`、`index`、`k` | 初始化回填 + 增量 | 可校验 |
| 分时 | `minute`、`minutes` | 盘中/盘后补采 | 接口已知存在异常风险 |
| 分笔 | `transaction`、`transactions` | 分页轮询 + 盘后补采 | 非 Level-2，不保证无遗漏 |
| 证券列表 | `stocks`、`stock_all` | 每日同步，仅保留沪深 A 股 | MOOTDX 候选集合 |
| 板块 | `block`、Reader block | 每日版本化 | 依赖 TDX 文件 |
| F10 | `F10C`、`F10` | 沪深证券目录哈希变化后抓取 | 按证券记录覆盖 |
| 除权除息 | `xdxr` | 每日同步 | MOOTDX 单源 |
| 财务摘要 | `finance` | 每日同步 | MOOTDX 单源 |
| 专业财务文件 | `Affair.files/fetch/parse` | 文件哈希增量 | 原文件永久保留 |
| 本地行情文件 | `Reader` | 文件变化监听 | 需要有效 `vipdoc` |

沪深证券列表来自 MOOTDX/TDX，按 `60/68` 和 `00/30` 前缀筛选候选集合。
Provider 在沪深范围内的能力必须在 `provider_capability` 中显式登记，
接口不得返回虚构空值，也不得把候选集合描述为交易所权威全集。

## 5. 数据封装

所有采集事件使用统一信封：

```json
{
  "event_id": "uuid",
  "provider": "mootdx",
  "dataset": "quote",
  "market": "CN",
  "exchange": "SSE",
  "symbol": "600519",
  "source_time": "2026-09-20T01:31:02.000Z",
  "collected_at": "2026-09-20T01:31:02.412Z",
  "server": "masked-server-id",
  "request": {"batch_id": "uuid", "offset": 0},
  "schema_version": 1,
  "payload_hash": "sha256:...",
  "payload": {}
}
```

`server` 使用内部别名，不向前端暴露公网地址。价格和数量进入标准层时使用
Decimal，禁止以二进制浮点作为持久化事实。

## 6. 分类型存储设计

### 6.1 MySQL

| 表 | 用途 |
| --- | --- |
| `instrument` | 当前证券主数据 |
| `instrument_mapping` | Provider 代码映射 |
| `provider_capability` | Provider、市场和数据类型能力 |
| `source_endpoint` | mootdx 服务器健康与延迟摘要 |
| `collector_job` | 采集任务定义与状态 |
| `collector_checkpoint` | 分片、分页和文件游标 |
| `backfill_job` | 人工/自动补采任务 |
| `data_quality_issue` | 缺口、冲突和处置状态 |
| `f10_document` | F10 标题、版本、对象引用和哈希 |
| `raw_object_manifest` | MinIO 对象、大小、哈希和生命周期 |

### 6.2 ClickHouse

| 表 | 分区 | 排序键 |
| --- | --- | --- |
| `market_quote_raw` | `toDate(collected_at)` | `(exchange, symbol, source_time, collected_at)` |
| `market_quote` | `toYYYYMM(source_time)` | `(exchange, symbol, source_time)` |
| `market_transaction` | `toDate(event_time)` | `(exchange, symbol, event_time, source_offset)` |
| `market_bar` | `toYYYYMM(event_time)` | `(exchange, symbol, interval, adjustment, event_time)` |
| `corporate_action` | `toYYYYMM(event_date)` | `(exchange, symbol, event_date, category)` |
| `financial_metric` | `toYYYYMM(report_date)` | `(symbol, report_date, metric_id)` |
| `block_membership_history` | `toYYYYMM(valid_from)` | `(block_code, symbol, valid_from)` |
| `ingest_observation` | `toDate(observed_at)` | `(dataset, observed_at, shard_id)` |

标准行情表使用 `ReplacingMergeTree(ingested_at)`，但查询不得依赖后台合并完成；
API 必须按幂等键取最新版本。原始表使用追加写入，不做物理覆盖。

### 6.3 MinIO

```text
market-raw/
  provider=mootdx/dataset=quote/trade_date=YYYY-MM-DD/hour=HH/batch_id.ndjson.zst
  provider=mootdx/dataset=transaction/trade_date=YYYY-MM-DD/symbol=XXXXXX/part.parquet
  provider=mootdx/dataset=f10/symbol=XXXXXX/content_hash.txt.zst
  provider=mootdx/dataset=financial/report_date=YYYY-MM-DD/source.zip
  provider=mootdx/dataset=reader/trade_date=YYYY-MM-DD/source-file
```

对象写入后计算 SHA-256，并在 MySQL 清单表登记。对象名不包含 Token、本地绝对
路径或真实服务器地址。

### 6.4 Redis

```text
cnmd:quote:latest:{exchange}:{symbol}
cnmd:quality:latest:{exchange}:{symbol}
cnmd:stream:sequence:{channel}
cnmd:collector:lease:{shard_id}
```

最新行情 TTL 设置为 15 分钟；闭市后由最后一条正式快照重建。Redis AOF 仅用于
缩短恢复时间，不能替代 ClickHouse。

## 7. 采集调度

### 7.1 实时快照

- 交易时段将沪深全部有效证券按交易所和代码哈希分片。
- 每个分片维持独立连接，批量调用 `quotes`。
- 调度目标是 2 秒内完成一轮，为 P95 3 秒预留处理和推送时间。
- 每轮记录应采证券数、实采证券数、空响应数、开始/结束时间和服务器。
- 单个服务器连续失败后熔断并切换，不在失败节点上无界重试。
- 应采、实采、缺口和聚合状态仅统计 SSE/SZSE。范围外市场不产生补采任务，
  也不因其未采集将沪深完整轮次标为 `partial`。

全市场 3 秒目标必须通过真实网络压测后才能标记为 Verified。公共行情服务器
无法满足时，系统继续运行但标记 `degraded`。

### 7.2 分笔

- 按证券保存 `start/offset` 游标和最后一条内容指纹。
- 盘中轮询所有证券，但不承诺 3 秒或 Level-2 完整性。
- 自选股和策略池使用高优先级队列，其余证券使用后台轮询。
- 收盘后按交易日执行历史分笔补采并生成覆盖报告。

### 7.3 历史与低频数据

| 数据 | 调度 |
| --- | --- |
| 1/5 分钟线 | 每分钟增量，收盘后校正 |
| 其他 K 线 | 周期结束后增量，收盘后统一校正 |
| 证券列表、状态、代码映射 | 每交易日前和收盘后 |
| 板块及成分 | 每日一次，内容变化时建新版本 |
| 除权除息 | 每日一次，除权日前加强校验 |
| F10 | 每周扫描目录，哈希变化时下载正文 |
| 财务摘要 | 每日收盘后 |
| Affair 文件 | 每日检查文件列表和 MD5 |
| Reader 文件 | 文件系统变更后导入，收盘后兜底扫描 |

## 8. 数据质量

质量状态：

```text
healthy | stale | partial | conflict | invalid | unavailable
```

校验规则：

- 源时间不得显著晚于采集时间。
- 开高低收必须满足 OHLC 关系。
- 交易时段累计成交量和成交额不得回退。
- 买一不得长期高于卖一；集合竞价等特殊时段按市场状态处理。
- 价格必须满足证券价格精度和当日涨跌幅规则。
- 快照、分钟线和日线的成交量单位必须统一为股。
- 快照与 MOOTDX 日 K 的交易日、收盘价和成交字段不一致时生成质量事件。

`stale`、`invalid` 和高严重度 `conflict` 数据不得触发开仓分析。原始记录始终
保留，质量判断只影响标准视图和下游使用。

## 9. API 与事件

### 9.1 REST

```text
GET  /api/v1/market/instruments
GET  /api/v1/market/quotes
GET  /api/v1/market/quotes/{instrument_id}
GET  /api/v1/market/bars/{instrument_id}
GET  /api/v1/market/transactions/{instrument_id}
GET  /api/v1/market/fundamentals/{instrument_id}
GET  /api/v1/market/f10/{instrument_id}
GET  /api/v1/market/data-catalog
GET  /api/v1/market/operations/collectors
GET  /api/v1/market/operations/quality-issues
POST /api/v1/market/operations/backfills
```

全市场接口的证券、交易所筛选和补采范围仅允许 SSE/SZSE。
接口必须分页、限制可排序字段，并返回 `as_of`、`freshness_ms`、
`quality_status` 和 `coverage_status`。

### 9.2 WebSocket

```text
quotes:cn:all
quotes:cn:watchlist:{watchlist_id}
quotes:cn:strategy:{strategy_id}
quality:cn
backfills:{job_id}
```

上述 `cn` 行情及质量频道仅覆盖沪深 A 股。消息包含单调递增的频道序列号。
客户端发现跳号后暂停增量合并，调用 REST
获取快照，再从新序列继续。

### 9.3 Kafka Topics

```text
market.raw.received.v1
market.quote.updated.v1
market.transaction.received.v1
market.bar.updated.v1
market.reference.updated.v1
market.quality.changed.v1
market.backfill.status_changed.v1
```

行情主题按 `exchange:symbol` 作为 Key 分区，确保单证券事件有序。

## 10. 前端交互设计

### 10.1 页面结构

现有 `/data` 改为二级路由：

```text
/data/market                 全市场
/data/stocks/:instrumentId   个股分析
/data/catalog                数据目录
/data/operations             数据运维
/settings/data-sources       数据源设置
```

### 10.2 全市场

- 顶部仅保留市场状态、覆盖证券数、P95 新鲜度和质量异常数。
- 主体为高密度虚拟表格，不使用卡片网格。
- 支持证券搜索、交易所（上交所/深交所）、行业、板块、涨跌幅、成交额和质量状态筛选。
- 支持固定证券列、列排序、列显隐和键盘导航。
- 仅对视口内行执行高频 DOM 更新；排序按节流窗口重排，避免价格变化导致行抖动。
- 点击证券进入个股分析；星标和加入策略池使用图标按钮并提供 Tooltip。

### 10.3 个股分析

- 顶部固定显示证券名、代码、最新价、涨跌幅、源时间和质量状态。
- 主区使用 Lightweight Charts 展示分时和 K 线。
- 右侧使用固定宽度盘口和实时分笔列表，不放入嵌套卡片。
- 下部按 Tab 展示财务、除权除息、F10 和数据来源。
- 图表周期、复权方式使用分段控件；价格与数量使用等宽字体。

### 10.4 数据目录与运维

- 数据目录展示数据集、来源、频率、历史范围、最新时间和字段定义。
- 运维页展示采集分片、服务器健康、吞吐、延迟、空响应、缺口和存储容量。
- 缺口行可创建补采任务，并展示明确的范围、预计请求量和状态。
- 严重异常使用文字、图标和颜色共同表达。

### 10.5 视觉规范

沿用现有 `tokens.css` 的冷白背景、深色 Appbar 和蓝色操作色。行情涨跌使用
独立语义：A 股上涨红、下跌绿，不复用系统成功/失败颜色。中文文本继续使用
Inter、SF Pro Text、苹方组合，行情数字使用等宽字体。布局以留白和细线分层，
卡片圆角不超过 8 px，除独立重复项外不增加阴影。

移动端优先提供自选股、个股行情、质量告警和补采状态；全市场宽表使用固定
证券列和横向滚动，不尝试压缩所有列。

## 11. 容量与部署

按约 5,400 只沪深证券的容量假设、每 3 秒一轮、每日 4 小时连续交易估算，未经快照去重时
约产生 2,600 万条快照/交易日。实际存储量取决于字段宽度、压缩率和相同快照
比例，容量验收前不得承诺固定年成本。真实应采数量使用当日沪深证券全集，
不以容量假设或范围外交易所证券数量替代。

初始部署建议：

- ClickHouse 单节点，数据目录使用独立 SSD 卷。
- MinIO 使用独立数据卷保存原始层和冷数据。
- ClickHouse 热数据 90 天，旧分区迁移到低成本本地磁盘或 MinIO。
- 初期磁盘预留不低于 2 TB，并通过首个完整交易周实测推算年度容量。
- 磁盘使用率 70% 告警、80% 停止非关键回填、90% 停止原始数据之外的派生写入。

## 12. 故障与恢复

- 采集进程先写本地 WAL，再发送 Kafka；发送成功后推进游标。
- Kafka 消费者使用幂等键，崩溃重启可重复消费。
- ClickHouse 不可用时原始数据继续进入 MinIO，恢复后重放。
- MinIO 不可用时保留本地 WAL，不确认采集批次完成。
- Redis 丢失时从 ClickHouse 最新标准记录重建。
- 单个 mootdx 服务器失效时自动切换；全部失效时数据状态变为 `unavailable`。

## 13. 可观测性

核心指标：

- `market_data_freshness_ms`
- `collector_batch_duration_ms`
- `collector_expected_symbols`
- `collector_received_symbols`
- `provider_empty_response_total`
- `provider_failover_total`
- `normalization_rejected_total`
- `data_quality_issue_total`
- `kafka_consumer_lag`
- `clickhouse_insert_latency_ms`
- `raw_archive_backlog_bytes`
- `websocket_sequence_gap_total`

日志禁止记录完整本地路径、真实节点地址和原始 F10 正文。

## 14. 已知风险

1. mootdx 项目当前版本为 0.11.7，外部服务器和协议变化可能导致失效。
2. 公共通达信服务器可能限流或返回空数据，3 秒目标必须实测。
3. MOOTDX/TDX 证券列表是前缀筛选后的候选集合，不具备交易所权威全集保证。
4. 分笔接口是查询接口，不是带序号重传能力的 Level-2 流。
5. 全量长期保存需要持续扩容和备份，单机磁盘是主要容量风险。

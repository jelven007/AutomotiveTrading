# MOOTDX 分时、历史日 K 与分笔接入设计

<!-- markdownlint-disable MD013 -->

> 状态：Approved for implementation
>
> 日期：2026-09-20
>
> 需求基线：`docs/requirements/a-share-market-data-requirements.md`

## 1. 目标与本期边界

本期在现有全沪深实时快照链路上增加三个可持续运行的数据集：

- 每只证券最近 800 根未复权日 K；
- 最近交易日 240 个分时点；
- 最近交易日最多 8 页、每页 800 条分笔。

采集范围仍只包含 MOOTDX/TDX 返回并按代码前缀筛选出的 SSE、SZSE 候选证券。
分笔接口没有交易所逐笔序号，也不是 Level-2 推送流；达到页数上限、出现非法时间或
非法买卖方向时必须标记 `partial`。本期不把“全部 K 线周期、复权 K 线、多交易日
分时和分笔”声明为已完成，这些仍是后续需求。

## 2. 方案选择

### 2.1 备选方案

1. 一次性全量回填全部周期和全部历史：覆盖最广，但会产生数千万级请求和记录，
   公共 TDX 节点、SQLite 队列及本地磁盘均不可控。
2. 仅在用户打开个股时抓取：首屏快，但数据不可预期，无法形成全市场覆盖进度。
3. 独立限速线程渐进回填：实时快照不等待历史任务，按持久化游标逐只推进，查询始终
   返回已完成部分及明确状态。

采用方案 3。它保留全市场最终覆盖目标，同时把源站压力、磁盘增长和失败恢复控制在
有界范围内。

## 3. 组件与数据流

```text
MOOTDX public nodes
  |-- quote connections --------> 2 s snapshot loop
  `-- history connections ------> bounded history worker
                                  | daily bars
                                  | minute timeline
                                  ` paged transactions
                                           |
                                      SQLite WAL
                                           |
                                authenticated HTTP batches
                                           |
                                 instrument-market
                                  | raw history rows
                                  | canonical rows
                                  ` coverage reports
                                           |
                                      ClickHouse
                                           |
                              REST history query endpoints
                                           |
                               React instrument detail
```

历史线程使用独立 `Provider` 和连接，不占用快照线程池。每完成一只证券，Sidecar 将
三个数据集的原始响应先写入 SQLite，再原子推进 `history_cursor`。网络或核心服务
失败时沿用现有发送队列重试；进程重启从游标继续。

## 4. Provider 语义

| 数据集 | tdxpy 方法 | 规则 |
| --- | --- | --- |
| 日 K | `get_security_bars(9, market, code, 0, 800)` | 服务端单页上限 800 |
| 分时 | `get_history_minute_time_data(market, code, YYYYMMDD)` | 正常交易日应为 240 点 |
| 分笔 | `get_history_transaction_data(market, code, start, 800, date)` | 短页结束，最多 8 页 |

分时响应没有时间字段，按 A 股连续竞价分钟映射：索引 0 到 119 对应
09:31 到 11:30，索引 120 到 239 对应 13:01 到 15:00。历史日 K 的成交量和
分时/分笔成交量按证券 `volunit` 转为股；原始数值和换算因子保留在元数据中。

分笔 `buyorsell` 仅接受 `0/1/2`，分别标准化为 `buy/sell/neutral`。非法时间、
非法方向、非正价格或负成交量只进入原始层，不进入标准层，并写入拒绝计数。

## 5. 存储与幂等

新增 `market_history_raw` 保存三个数据集的原始行、请求参数、批次、来源节点和哈希。
新增 `market_minute` 保存分时点。扩展 `market_bar`、`market_transaction`，增加
`source_id`、`batch_id`、质量状态和采集完整性字段。

核心使用现有 MySQL `ingest_receipt`：

- 相同批次、相同正文重复发送时直接返回首次结果；
- 相同批次、不同正文返回 409；
- 原始行事件 ID 由 `batch_id + row_index` 稳定生成；
- 标准表使用 `ReplacingMergeTree(ingested_at)`，查询显式按最新版本聚合。

## 6. 查询 API

```text
GET /api/v1/market/bars/{exchange}/{symbol}?interval=1d&limit=240
GET /api/v1/market/minutes/{exchange}/{symbol}?trade_date=YYYY-MM-DD
GET /api/v1/market/transactions/{exchange}/{symbol}?trade_date=YYYY-MM-DD&limit=200
```

所有接口校验交易所、六位证券代码和行数上限。响应包含 `provider`、`source_id`、
`trade_date`、`coverage` 与 `items`。没有数据时返回空数组和 `pending`，不返回
虚构价格。

## 7. 前端

行情表行可选中；页面下方展开个股工作区，使用紧凑标签切换“分时”“日 K”“分笔”。
分时采用价格折线与成交量，日 K 采用金融蜡烛图，分笔使用定高滚动列表。整体延续
现有低圆角、细分隔线和高密度工作台风格，不新增营销式卡片或装饰。

桌面为图表与盘口数据并排的工作区，移动端改为单列。加载、无数据、`partial`、
错误和重试状态均占据稳定高度，切换标签时不推动页面主体。

## 8. 验证

- 单元测试覆盖 800 条边界、240 点时间映射、分页短页、8 页截断、非法分笔、
  SQLite 检查点和批次重放。
- 核心测试覆盖原始先写、逐行拒绝、Decimal/时区/成交量换算、幂等接收及查询边界。
- Web 测试覆盖选中证券、三标签切换、空状态和 `partial` 提示。
- 真实验收至少使用沪深各一只证券，核对日 K、分时、分笔写入数量和查询结果；
  分笔仅验证“如实报告覆盖”，不声明 Level-2 完整。

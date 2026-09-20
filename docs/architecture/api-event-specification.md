# API 与事件规格说明书

> 文档编号：QT-API-001
>
> 版本：1.2-draft

## 1. 通用规范

- REST 基础路径：`/api/v1`
- 内容类型：`application/json`
- 时间：UTC ISO-8601
- 金额：Decimal 字符串
- ID：UUID
- 写请求头：`Idempotency-Key`
- 链路请求头：`Traceparent`
- 租户：从 Access Token 获取，不信任客户端自报租户

错误格式：

```json
{
  "type": "https://errors.quant-trading.local/model.config_not_active",
  "title": "Model configuration is unavailable",
  "status": 409,
  "detail": "模型配置不可用于当前环境",
  "code": "model.config_not_active",
  "trace_id": "uuid",
  "details": {}
}
```

## 2. 模型配置 API

```text
GET    /tenant/model-configurations
POST   /tenant/model-configurations
GET    /tenant/model-configurations/{id}
PATCH  /tenant/model-configurations/{id}
POST   /tenant/model-configurations/{id}/test
POST   /tenant/model-configurations/{id}/enable
POST   /tenant/model-configurations/{id}/disable
POST   /tenant/model-configurations/{id}/rotate-secret
DELETE /tenant/model-configurations/{id}
GET    /model-catalog
```

创建请求：

```json
{
  "name": "团队 GPT",
  "provider_type": "openai",
  "base_url": "https://api.openai.com/v1",
  "model_id": "model-name",
  "api_key": "write-only",
  "timeout_ms": 30000,
  "max_retries": 1,
  "max_concurrency": 10,
  "temperature": 0.1,
  "top_p": 1,
  "max_output_tokens": 1200,
  "rpm_limit": 60,
  "daily_token_limit": 1000000,
  "daily_cost_limit": "500.00",
  "allowed_environments": ["backtest", "simulation"],
  "enabled": false
}
```

响应不得包含 `api_key`，只返回：

```json
{
  "id": "uuid",
  "secret_status": "configured",
  "secret_updated_at": "ISO-8601"
}
```

Ollama/vLLM 一期规则：

- 允许保存。
- 校验 URL 和 Model ID 格式。
- `availability = planned`。
- `/test` 返回 `FEATURE_NOT_AVAILABLE`。
- 不出现在策略可选模型列表。

## 3. 策略 API

```text
POST   /strategies
GET    /strategies
GET    /strategies/{id}
PATCH  /strategies/{id}
POST   /strategies/{id}/validate
POST   /strategies/{id}/versions
GET    /strategies/{id}/versions
POST   /strategies/{id}/backtests
POST   /strategies/{id}/deployments
POST   /strategies/{id}/pause
POST   /strategies/{id}/archive
```

发布版本请求必须包含当前草稿版本号，避免覆盖并发修改。

## 4. AI 决策 API

```text
POST /strategies/{id}/analyze
GET  /model-decisions
GET  /model-decisions/{id}
POST /model-decisions/{id}/confirm
POST /model-decisions/{id}/reject
```

模型决策：

```json
{
  "id": "uuid",
  "strategy_version_id": "uuid",
  "instrument_id": "uuid",
  "action": "buy",
  "confidence": 0.82,
  "target_position_pct": 0.15,
  "order_type": "limit",
  "limit_price": "12.30",
  "valid_until": "2026-09-18T07:00:00Z",
  "reasons": ["string"],
  "risk_flags": [],
  "status": "candidate|coordinated|rejected|confirmed|expired"
}
```

## 5. 交易 API

```text
GET    /trading/binance/accounts
POST   /trading/binance/accounts
PUT    /trading/binance/accounts/{id}
DELETE /trading/binance/accounts/{id}
POST   /trading/binance/accounts/{id}/test
POST   /trading/binance/accounts/{id}/activate
POST   /trading/binance/accounts/active/deactivate
GET    /trading/binance/status
GET    /trading/binance/balances
GET    /trading/binance/positions
GET    /trading/binance/orders
POST   /trading/binance/orders
POST   /trading/binance/orders/{id}/cancel
PUT    /trading/binance/futures/{symbol}/leverage
PUT    /trading/binance/futures/{symbol}/margin-mode
GET    /trading/binance/risk
PUT    /trading/binance/risk
POST   /trading/binance/emergency-stop
DELETE /trading/binance/emergency-stop
```

币安帐号绑定请求：

```json
{
  "alias": "main-binance",
  "credential_type": "ed25519|hmac",
  "api_key": "write-only",
  "secret": "write-only",
  "ip_whitelist_confirmed": true,
  "withdrawal_disabled_confirmed": true
}
```

响应不得返回 `api_key`、私钥、Secret、密文或 nonce，只返回帐号 ID、别名、
脱敏指纹、Spot/USD-M 可用状态、连接状态和是否为当前帐号。管理员必须完成人工
IP 白名单和禁止提现确认；未完成近期 MFA 时，帐号写操作必须失败。

下单请求：

```json
{
  "product": "spot|usdm_futures",
  "instrument_id": "BTCUSDT.BINANCE",
  "side": "buy|sell",
  "order_type": "market|limit|stop_market|stop_limit",
  "quantity": "0.001",
  "limit_price": "60000",
  "time_in_force": "GTC",
  "position_side": "both|long|short|null",
  "reduce_only": false,
  "source": "manual|strategy"
}
```

币安请求规则：

- 所有读取和执行均通过当前活动帐号的 Nautilus Runtime。
- 现货 instrument 使用 `BTCUSDT.BINANCE`；U 本位永续使用
  `BTCUSDT-PERP.BINANCE`。
- `product=usdm_futures` 时必须校验持仓模式、保证金模式和本地杠杆上限。
- `reduce_only` 仅用于合约风险降低语义。
- 下单、撤单、杠杆和保证金模式调整必须使用独立 `Idempotency-Key`。
- 外部结果不确定时返回 `pending_reconciliation`，不得自动重放。
- 现货借款、还款、划转及现货杠杆请求不属于当前 API。

## 6. WebSocket

连接：

```text
GET /ws/v1?access_token=<short-lived-token>
```

频道：

- `quotes:{instrument_id}`
- `quotes:cn:all`
- `quotes:cn:watchlist:{watchlist_id}`
- `quotes:cn:strategy:{strategy_id}`
- `quality:cn`
- `backfills:{job_id}`
- `backtests:{task_id}`
- `orders:{account_id}`
- `balances:{account_id}`
- `futures-positions:{account_id}`
- `binance-runtime`
- `alerts:{tenant_id}`
- `strategies:{strategy_id}`

客户端必须支持断线重连、序列号检查和 REST 补偿查询。

A 股行情 REST、WebSocket 和事件契约的专项设计见
[`QT-DES-CNMD-001`](../plans/2026-09-20-a-share-market-data-design.md)。
按 2026-09-20 确认的范围，A 股证券、行情查询、补采请求和 `cn` 行情频道
仅覆盖 SSE/SZSE，交易所筛选与覆盖统计同样限定沪深。
全市场频道只发送增量变化，客户端发现序列号缺口后必须停止合并并重新获取
REST 快照。

## 7. 事件信封

```json
{
  "event_id": "uuid",
  "event_type": "order.status_changed.v1",
  "event_version": 1,
  "occurred_at": "ISO-8601",
  "tenant_id": "uuid",
  "trace_id": "uuid",
  "actor": {
    "type": "user|service|strategy",
    "id": "uuid"
  },
  "payload": {}
}
```

## 8. 关键事件 Payload

### 8.1 strategy.analysis.requested.v1

```json
{
  "analysis_id": "uuid",
  "strategy_version_id": "uuid",
  "instrument_id": "uuid",
  "trigger_type": "schedule|market_event|manual",
  "market_timestamp": "ISO-8601",
  "idempotency_key": "string"
}
```

### 8.2 order.status_changed.v1

```json
{
  "order_id": "uuid",
  "broker_order_id": "string|null",
  "from_status": "submitted",
  "to_status": "partially_filled",
  "filled_quantity": "50",
  "average_price": "12.31",
  "broker_timestamp": "ISO-8601"
}
```

### 8.3 reconciliation.mismatch_detected.v1

```json
{
  "incident_id": "uuid",
  "account_id": "uuid",
  "category": "cash|position|order|execution|fee",
  "severity": "medium|high|critical",
  "expected": {},
  "actual": {}
}
```

### 8.4 trading.account_bound.v1

```json
{
  "account_id": "uuid",
  "provider": "binance",
  "environment": "production",
  "credential_type": "ed25519|hmac",
  "products": ["spot", "usdm_futures"],
  "active": false
}
```

### 8.5 binance.runtime_changed.v1

```json
{
  "account_id": "uuid",
  "spot_status": "ready|disconnected|stale|error",
  "futures_status": "ready|disconnected|stale|error",
  "reconciliation_status": "pending|running|completed|failed",
  "accepting_orders": false,
  "occurred_at": "ISO-8601"
}
```

### 8.6 futures.position_changed.v1

```json
{
  "account_id": "uuid",
  "symbol": "BTCUSDT",
  "position_side": "both|long|short",
  "margin_mode": "cross|isolated",
  "leverage": 5,
  "quantity": "0.010",
  "mark_price": "62000.00",
  "liquidation_price": "51000.00",
  "unrealized_pnl": "15.20",
  "occurred_at": "ISO-8601"
}
```

## 9. 兼容性

- REST 只允许向后兼容地新增可选字段。
- 删除或变更语义必须发布新 API 版本。
- Protobuf 字段号不得复用。
- Kafka 事件不得改变既有字段语义。
- Schema Registry 校验生产者向后兼容。

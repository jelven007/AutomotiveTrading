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

币安阶段一：

```text
GET    /trading/binance/account
PUT    /trading/binance/account
DELETE /trading/binance/account
GET    /trading/binance/overview
GET    /trading/binance/overview?refresh=true
```

币安阶段二：

```text
GET    /trading/binance/orders
POST   /trading/binance/orders
POST   /trading/binance/orders/{id}/cancel
PUT    /trading/binance/futures/{symbol}/leverage
PUT    /trading/binance/futures/{symbol}/margin-mode
```

币安帐号首次绑定和重新绑定使用同一请求：

```json
{
  "alias": "main-binance",
  "api_key": "write-only",
  "api_secret": "write-only",
  "ip_whitelist_confirmed": true
}
```

响应不得返回 `api_key`、Secret、密文或 nonce，只返回别名、脱敏指纹、连接状态
和最近验证时间。每个用户只允许一条币安帐号记录。新凭据完成权限检查和候选
Nautilus Runtime 验证后，才允许原子覆盖旧帐号；失败时旧帐号保持可用。

`GET /overview` 一次返回权限、现货余额、U 本位余额和非零持仓。每个区域包含
独立的 `status`、`data` 和可选 `error`；Spot 或 USD-M 单侧失败时，HTTP 响应
仍返回其他可用区域。`refresh=true` 仅绕过最多 5 秒的进程内快照，不持久化
账户数据。

下单请求：

```json
{
  "product": "spot|usdm_futures",
  "instrument_id": "BTCUSDT.BINANCE",
  "side": "buy|sell",
  "order_type": "market|limit",
  "quantity": "0.001",
  "limit_price": "60000",
  "time_in_force": "GTC"
}
```

币安请求规则：

- 权限由最小签名 REST 探测，余额、持仓和执行通过唯一帐号的 Nautilus Runtime。
- 现货 instrument 使用 `BTCUSDT.BINANCE`；U 本位永续使用
  `BTCUSDT-PERP.BINANCE`。
- 阶段一不注册任何币安交易写接口。
- 阶段二仅接受人工来源，并要求有效的短时 MFA 交易会话。
- 下单、撤单、杠杆和保证金模式调整必须使用独立 `Idempotency-Key`。
- 外部结果不确定时返回 `pending_reconciliation`，不得自动重放。
- 批量撤单、条件单、双向持仓、现货杠杆、借还款和资产划转不属于当前 API。

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
- `orders:{account_id}`，仅阶段二启用
- `alerts:{tenant_id}`
- `strategies:{strategy_id}`

客户端必须支持断线重连、序列号检查和 REST 补偿查询。
币安阶段一账户查询不使用 WebSocket 页面频道。

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

# API 与事件规格说明书

> 文档编号：QT-API-001
>
> 版本：1.1-draft

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
  "code": "MODEL_CONFIG_NOT_ACTIVE",
  "message": "模型配置不可用于当前环境",
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
GET    /trading/accounts
POST   /trading/accounts/bind
POST   /trading/accounts/{id}/test
POST   /trading/accounts/{id}/enable-trading
POST   /trading/accounts/{id}/connect
POST   /trading/accounts/{id}/disconnect
GET    /trading/accounts/{id}/balances
GET    /trading/accounts/{id}/margin-risk
GET    /trading/accounts/{id}/futures-positions
POST   /trading/accounts/{id}/transfers
POST   /trading/accounts/{id}/margin-loans
POST   /trading/accounts/{id}/margin-repayments
PUT    /trading/accounts/{id}/futures-settings
GET    /trading/positions
GET    /trading/orders
POST   /trading/orders
GET    /trading/orders/{id}
POST   /trading/orders/{id}/cancel
GET    /trading/executions
POST   /trading/kill-switch
DELETE /trading/kill-switch/{id}
```

币安帐号绑定请求：

```json
{
  "market_group": "binance",
  "provider": "binance",
  "environment": "production",
  "credential_type": "ed25519|hmac|rsa",
  "api_key": "write-only",
  "private_key_or_secret": "write-only",
  "enabled_scopes": [
    "spot",
    "cross_margin",
    "isolated_margin",
    "usdm_futures"
  ],
  "ip_whitelist_confirmed": true
}
```

响应不得返回 `api_key`、私钥或 Secret，只返回脱敏指纹、KMS 引用状态、
权限检查结果和帐号 Scope。具有提现权限、未配置固定出口 IP 白名单或未完成
近期 MFA 时，绑定或启用生产交易必须失败。

下单请求：

```json
{
  "account_id": "uuid",
  "instrument_id": "uuid",
  "account_scope": "spot|cross_margin|isolated_margin|usdm_futures",
  "side": "buy|sell",
  "order_type": "market|limit",
  "quantity": "100",
  "limit_price": "12.30",
  "margin_mode": "cross|isolated|null",
  "position_side": "both|long|short|null",
  "reduce_only": false,
  "margin_side_effect": "none|borrow|repay|auto_borrow_repay",
  "decision_id": "uuid|null",
  "source": "manual|strategy"
}
```

币安请求规则：

- `account_scope=isolated_margin` 时必须提供交易对并使用逐仓资产。
- `account_scope=usdm_futures` 时必须校验持仓模式、保证金模式和杠杆配置。
- `reduce_only` 仅用于合约风险降低语义，双向持仓模式按币安约束处理。
- 借款、还款、划转、杠杆调整和生产写权限启用必须使用独立
  `Idempotency-Key`。
- 外部超时统一返回 `order_status=unknown`，不得自动重放。

## 6. WebSocket

连接：

```text
GET /ws/v1?access_token=<short-lived-token>
```

频道：

- `quotes:{instrument_id}`
- `backtests:{task_id}`
- `orders:{account_id}`
- `balances:{account_id}`
- `margin-risk:{account_id}`
- `futures-positions:{account_id}`
- `alerts:{tenant_id}`
- `strategies:{strategy_id}`

客户端必须支持断线重连、序列号检查和 REST 补偿查询。

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
  "credential_type": "ed25519",
  "enabled_scopes": ["spot", "cross_margin", "isolated_margin", "usdm_futures"],
  "trading_enabled": false
}
```

### 8.5 margin.risk_changed.v1

```json
{
  "account_id": "uuid",
  "account_scope": "cross_margin|isolated_margin",
  "symbol": "BTCUSDT|null",
  "margin_level": "1.42",
  "status": "normal|margin_call|pre_liquidation|force_liquidation",
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

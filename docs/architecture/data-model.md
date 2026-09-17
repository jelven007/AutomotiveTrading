# 核心数据模型说明书

> 文档编号：QT-DM-001
>
> 版本：1.0-draft

## 1. 建模规则

- 所有租户数据包含 `tenant_id`。
- 主键使用 UUID。
- 时间使用 UTC，另存市场时区。
- 金额和数量使用 Decimal。
- 软删除对象包含 `deleted_at`，交易流水禁止删除。
- 敏感值只保存 KMS Secret 引用。
- 跨服务只保存外部 ID，不建立跨库外键。

## 2. 身份与租户

### tenant

```text
id, name, status, plan_id, created_at, updated_at
```

### user

```text
id, email, display_name, status, mfa_enabled, created_at
```

### tenant_member

```text
tenant_id, user_id, role, status, joined_at
UNIQUE(tenant_id, user_id)
```

## 3. 模型配置

### model_configuration

```text
id
tenant_id
name
provider_type
base_url
model_id
secret_ref
timeout_ms
max_retries
max_concurrency
temperature
top_p
max_output_tokens
rpm_limit
daily_token_limit
daily_cost_limit
allowed_environments_json
availability
enabled
health_status
last_tested_at
version
created_by
created_at
updated_at
```

约束：

- `UNIQUE(tenant_id, name)`
- `provider_type` 为枚举。
- Ollama/vLLM 一期 `availability = planned`。
- API Key 不进入数据库。

### model_invocation

```text
id, tenant_id, model_configuration_id, strategy_version_id, instrument_id,
trigger_id, prompt_version, request_object_ref, response_object_ref,
input_tokens, output_tokens, cost, latency_ms, status, error_code, created_at
```

## 4. 证券与行情

### instrument

```text
id, market, exchange, symbol, name, currency, timezone, lot_size, status
UNIQUE(market, exchange, symbol)
```

### instrument_mapping

```text
id, instrument_id, provider_type, provider_code, valid_from, valid_to, status
UNIQUE(provider_type, provider_code, valid_from)
```

### market_bar

ClickHouse 排序键建议：

```text
(market, instrument_id, interval, event_time)
```

字段：

```text
instrument_id, interval, event_time, open, high, low, close, volume, turnover,
adjustment, provider, source_version, ingested_at
```

## 5. 策略

### strategy

```text
id, tenant_id, name, description, owner_id, lifecycle_status,
current_draft_version, created_at, updated_at
```

### strategy_version

```text
id, tenant_id, strategy_id, version_number, source_object_ref,
parameter_schema_json, parameter_values_json, universe_snapshot_ref,
model_configuration_id, prompt_template, output_schema_version,
execution_mode, risk_policy_id, checksum, published_by, published_at
UNIQUE(tenant_id, strategy_id, version_number)
```

### strategy_trigger

```text
id, tenant_id, strategy_version_id, trigger_type, expression_json,
cooldown_seconds, daily_limit, enabled
```

## 6. AI 决策

### model_decision

```text
id, tenant_id, analysis_id, strategy_version_id, instrument_id,
model_invocation_id, action, confidence, target_position_pct, order_type,
limit_price, valid_until, reasons_json, risk_flags_json, data_timestamp,
status, created_at
```

幂等唯一键：

```text
UNIQUE(tenant_id, strategy_version_id, instrument_id, trigger_type,
       market_timestamp)
```

### portfolio_decision

```text
id, tenant_id, strategy_version_id, decision_batch_id, instrument_id,
model_decision_id, approved_action, approved_position_pct, adjustment_reason,
status, created_at
```

## 7. 交易

### trading_account

```text
id, tenant_id, broker_type, environment, external_account_ref, secret_ref,
currency, status, connection_status, last_synced_at
```

### order

```text
id, tenant_id, account_id, client_order_id, broker_order_id,
instrument_id, side, order_type, quantity, limit_price, filled_quantity,
average_price, status, source, decision_id, idempotency_key,
submitted_at, updated_at
UNIQUE(tenant_id, idempotency_key)
```

### execution

```text
id, tenant_id, account_id, order_id, broker_execution_id, quantity, price,
fee, tax, currency, executed_at
UNIQUE(tenant_id, account_id, broker_execution_id)
```

### position_snapshot

```text
tenant_id, account_id, instrument_id, total_quantity, sellable_quantity,
average_cost, market_value, unrealized_pnl, snapshot_at
```

### ledger_entry

```text
id, tenant_id, account_id, transaction_id, account_code, direction,
amount, currency, reference_type, reference_id, occurred_at
```

同一 `transaction_id` 借贷合计必须为零。

## 8. 风控与对账

### risk_policy

```text
id, tenant_id, name, scope_type, scope_id, rules_json, version, enabled,
created_by, updated_at
```

### risk_evaluation

```text
id, tenant_id, order_id, policy_id, policy_version, input_ref,
result, violations_json, evaluated_at
```

### reconciliation_incident

```text
id, tenant_id, account_id, category, severity, expected_json, actual_json,
status, restricted_at, resolved_at, resolution, resolved_by
```

## 9. 审计

### audit_record

建议写入追加型审计存储：

```text
id, tenant_id, actor_type, actor_id, action, resource_type, resource_id,
before_ref, after_ref, request_id, trace_id, ip_hash, occurred_at,
previous_hash, record_hash
```

`previous_hash` 和 `record_hash` 用于检测审计记录被篡改。

## 10. 数据保留

| 数据 | 默认保留 |
| --- | --- |
| 订单、成交、账本 | 不少于法定及合同要求 |
| 审计记录 | 套餐决定，实盘关键记录长期保留 |
| 模型输入输出 | 默认 180 天，可按合规延长 |
| 行情数据 | 依据授权和套餐 |
| 应用日志 | 30 至 90 天 |
| 安全日志 | 至少 180 天 |

最终期限必须经法务、合规和数据授权确认。

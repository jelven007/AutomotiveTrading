# 核心数据模型说明书

> 文档编号：QT-DM-001
>
> 版本：1.3-draft

## 1. 建模规则

- 所有租户数据包含 `tenant_id`。
- 主键使用 UUID。
- 时间使用 UTC，另存市场时区。
- 金额和数量使用 Decimal。
- 软删除对象包含 `deleted_at`，交易流水禁止删除。
- 敏感值不得明文保存；模型与其他券商使用 KMS，币安使用本地主密钥加密入库。
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
id, asset_class, market, exchange, symbol, base_asset, quote_asset, name,
currency, timezone, lot_size, price_tick, quantity_step, status
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

### A 股行情专项模型

该子域的数据范围为上交所（SSE）和深交所（SZSE）A 股，主数据、映射、
采集任务、回填及覆盖统计均按沪深证券限定。Provider 全集先按交易所筛选；
范围外市场不计入应采或缺口，遗留原始报告不因范围修订而改写。

mootdx 原始与标准化数据不得混用同一张表。专项模型包含：

```text
market_quote_raw
market_quote
market_transaction
corporate_action
financial_metric
block_membership_history
ingest_observation
provider_capability
collector_job
collector_checkpoint
backfill_job
data_quality_issue
f10_document
raw_object_manifest
```

其中高频事实写入 ClickHouse，控制面和当前主数据写入 MySQL，原始文件及
响应写入 MinIO，最新行情投影写入 Redis。完整字段、分区、排序键和保留策略
见 [`QT-DES-CNMD-001`](../plans/2026-09-20-a-share-market-data-design.md)。

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
id, tenant_id, market_group, provider, environment, external_account_ref,
credential_type, api_key_fingerprint, currency, status, connection_status,
is_active, spot_available, usdm_futures_available,
ip_whitelist_confirmed_at, withdrawal_disabled_confirmed_at,
last_tested_at, last_synced_at, created_by, created_at, updated_at
```

约束：

- `market_group` 为 `cn_equity|hk_us_equity|binance`。
- `provider` 一期为
  `tonghuashun|caixin|futu|longbridge|binance`。
- 币安生产帐号禁止保存明文 API Key、Secret 或私钥。
- 币安帐号支持 HMAC 和 Ed25519，不支持 RSA。
- 可以保存多个币安帐号，但只允许一个 `is_active=true`。
- 固定出口 IP 和禁止提现由管理员人工确认并记录确认时间。

### binance_encrypted_credential

```text
id, tenant_id, account_id, ciphertext, nonce, algorithm_version,
created_at, updated_at
UNIQUE(tenant_id, account_id)
```

密文由 AES-256-GCM 产生，`account_id`、凭据类型和算法版本作为附加认证数据。
主密钥来自 ECS 只读文件，不进入数据库。

### binance_runtime_state

```text
account_id, spot_status, futures_status, reconciliation_status,
accepting_orders, last_event_at, last_reconciled_at, updated_at
UNIQUE(account_id)
```

运行状态由 Nautilus 事件更新；状态过期或未完成对账时禁止新订单。

### order

```text
id, tenant_id, account_id, client_order_id, broker_order_id,
product, instrument_id, side, position_side, order_type, time_in_force,
quantity, limit_price, stop_price, reduce_only,
filled_quantity, average_price, status, source, decision_id, idempotency_key,
request_fingerprint, submitted_at, updated_at
UNIQUE(tenant_id, idempotency_key)
UNIQUE(tenant_id, account_id, client_order_id)
```

`product` 仅允许 `spot|usdm_futures`。不确定写入使用
`pending_reconciliation`，禁止自动重发。

### execution

```text
id, tenant_id, account_id, order_id, broker_execution_id, quantity, price,
fee, tax, currency, executed_at
UNIQUE(tenant_id, account_id, broker_execution_id)
```

### binance_risk_setting

```text
account_id, emergency_stop, max_order_notional, max_position_notional,
max_futures_leverage, max_daily_loss, updated_at
UNIQUE(account_id)
```

### position_snapshot

```text
tenant_id, account_id, instrument_id, total_quantity, sellable_quantity,
average_cost, market_value, unrealized_pnl, snapshot_at
```

### futures_position_snapshot

```text
id, tenant_id, account_id, instrument_id, position_side, margin_mode,
leverage, quantity, entry_price, mark_price, liquidation_price,
initial_margin, maintenance_margin, unrealized_pnl, snapshot_at
```

### funding_payment

```text
id, tenant_id, account_id, instrument_id, external_transaction_id,
funding_rate, amount, asset, occurred_at
UNIQUE(tenant_id, account_id, external_transaction_id)
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

# Risk Service 与 KMS Adapter 设计

> 文档编号：QT-DES-RSK-KMS-001
>
> 日期：2026-09-19
>
> 状态：已确认实施

## 1. 目标

新增两个独立微服务：

- `risk`：执行确定性交易规则，签发并消费短期风险审批令牌。
- `kms-adapter`：封装火山引擎 KMS，为业务服务提供租户隔离的 Secret Broker。

两者均不直接面向公网。Trading Service 通过独立服务身份调用，任一服务不可用时
生产写请求失败关闭。

## 2. Risk Service

### 2.1 数据所有权

Risk Service 拥有：

- 租户风险策略及版本。
- 订单风险评估记录。
- 风险审批令牌哈希、订单指纹、有效期和消费状态。
- 帐号保护状态和风险快照。

明文审批令牌只在签发响应中出现一次，数据库仅保存 SHA-256 哈希。

### 2.2 规则

首期确定性规则：

- 必须存在已启用的租户策略。
- 风险快照必须在允许的新鲜度内。
- Scope、交易对和订单来源必须在白名单内。
- 单笔名义金额、当日累计金额和预计持仓名义价值不得超限。
- 现货买入不得超过可用资金。
- 杠杆帐号风险率不得低于策略阈值。
- U 本位杠杆不得超过平台上限，强平距离和 ADL 风险必须满足阈值。
- 保护模式下只允许明确的 `reduceOnly`、撤单和还款操作。

所有 Decimal 计算使用字符串输入，禁止浮点数参与资金判断。

### 2.3 审批令牌

```text
Risk evaluation
  -> approved
  -> random token returned once
  -> token hash + order fingerprint persisted
  -> Trading verifies token with the exact order
  -> atomic mark consumed
```

令牌默认 60 秒过期且只能消费一次。租户、帐号、订单内容或用途任一不匹配均拒绝。

### 2.4 API

```text
PUT  /api/v1/risk/policies/{tenant_id}
GET  /api/v1/risk/policies/{tenant_id}
POST /api/v1/risk/order-authorizations
POST /api/v1/risk/order-authorizations/verify
GET  /health/live
GET  /health/ready
```

首期接口使用 `X-Service-Token` 认证。生产部署时令牌由 KMS/Secret 注入，并通过
NetworkPolicy 限制只有 Trading 和管理面可访问。

## 3. KMS Adapter

### 3.1 加密模型

采用火山引擎 KMS 信封加密：

1. Broker 为每个 Secret 调用 `GenerateDataKey`，长度固定为 32 字节。
2. 使用数据密钥明文和 AES-256-GCM 加密 JSON Secret。
3. 数据库保存业务密文、Nonce、加密后的数据密钥和加密上下文。
4. 解析时调用 `Decrypt` 解开数据密钥，再在内存中解密业务密文。
5. 数据密钥明文、API Key 和私钥不写日志、不写数据库、不进入异常详情。

加密上下文固定包含 `tenant_id`、`secret_id` 和 `purpose`。火山 KMS 解密时必须
提交完全一致的上下文，防止密文被移动到其他租户或用途。

### 3.2 Provider

定义最小 `KmsProvider`：

```text
generate_data_key(key_id, encryption_context) -> plaintext_dek, encrypted_dek
decrypt_data_key(encrypted_dek, encryption_context) -> plaintext_dek
```

生产实现使用火山引擎 KMS `2021-02-18` API。AK/SK/STS 只从进程环境或实例角色
获取，不进入 Broker 数据库。单元测试使用内存 Provider。

### 3.3 Broker API

```text
POST /v1/secrets
POST /v1/secrets/resolve
POST /v1/secrets/delete
GET  /health/live
GET  /health/ready
```

请求必须携带 `Authorization: Bearer <service-token>`。`secret_ref` 使用
`volc-kms://<tenant_id>/<secret_id>`，解析和删除时必须同时提交 `tenant_id`，
Broker 对引用中的租户与请求租户做常量时间比较。

删除采用不可恢复语义：清空业务密文、Nonce 和加密数据密钥，只保留资源 ID、
租户、状态和审计时间。

## 4. Trading 集成

- `HttpKmsSecretBackend` 增加租户参数和服务令牌。
- `HttpRiskAuthorizer` 增加 `X-Service-Token`。
- 生产配置要求 `KMS_SERVICE_TOKEN` 与 `RISK_SERVICE_TOKEN`。
- 风控审批令牌仍通过 `X-Risk-Approval` 传递，Risk Service 校验后单次消费。
- KMS 或 Risk 返回超时、非 2xx、无效 JSON 时均拒绝交易，不降级到本地实现。

## 5. 验证边界

自动化测试必须覆盖：

- Decimal 风控边界、快照过期、Scope/交易对越权和保护模式。
- 审批令牌过期、重放、订单篡改和跨租户使用。
- AES-GCM 密文随机性、AAD 租户隔离、删除后不可恢复。
- 火山 KMS 请求参数、加密上下文和错误脱敏。
- Trading 到两个服务的服务令牌和失败关闭。

真实火山 KMS 联调仍需要控制台资源、最小权限 IAM 身份和授权环境，不能由 CI
使用模拟凭据替代生产验收。

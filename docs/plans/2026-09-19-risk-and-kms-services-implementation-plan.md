# Risk Service 与 KMS Adapter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现可供 Trading Service 调用的确定性风控审批服务和火山引擎 KMS
信封加密适配服务。

**Architecture:** Risk Service 使用版本化租户策略和短期单次令牌；KMS Adapter
使用 AES-GCM 加密业务 Secret，并由火山 KMS 包装每条记录的数据密钥。两个服务
均使用独立服务令牌认证，任何依赖异常均失败关闭。

**Tech Stack:** FastAPI、Pydantic、SQLAlchemy、Alembic、cryptography、
httpx、Volcengine OpenAPI、pytest。

---

## Task 1: Risk 策略和确定性评估器

**Files:**

- Create: `services/risk/`
- Create: `services/risk/src/risk/models.py`
- Create: `services/risk/src/risk/policy.py`
- Create: `services/risk/tests/test_policy.py`
- Create: `services/risk/migrations/versions/0001_risk_core.py`

### Task 1, Step 1: 写失败测试

覆盖策略缺失、快照过期、Scope/交易对白名单、单笔和日累计限额、现货可用资金、
杠杆风险率、合约杠杆/强平距离/ADL，以及保护模式。

### Task 1, Step 2: 确认测试失败

Run: `uv run pytest services/risk/tests/test_policy.py -v`

Expected: FAIL，`risk` 领域模块不存在。

### Task 1, Step 3: 实现

所有金额使用 `Decimal`。评估返回稳定决策码和完整拒绝原因，不抛出包含帐号资金
明细的异常。

### Task 1, Step 4: 验证

Run: `uv run pytest services/risk/tests/test_policy.py -v`

Expected: PASS。

## Task 2: Risk 审批令牌和 API

**Files:**

- Create: `services/risk/src/risk/authorizations.py`
- Create: `services/risk/src/risk/api.py`
- Create: `services/risk/src/risk/security.py`
- Create: `services/risk/src/risk/main.py`
- Create: `services/risk/tests/test_authorizations.py`
- Create: `services/risk/tests/test_api.py`

### Task 2, Step 1: 写失败测试

验证服务认证、令牌只返回一次、数据库仅保存哈希、60 秒过期、单次消费、订单指纹
绑定、跨租户拒绝和并发消费。

### Task 2, Step 2: 确认测试失败

Run:

```bash
uv run pytest \
  services/risk/tests/test_authorizations.py \
  services/risk/tests/test_api.py -v
```

Expected: FAIL。

### Task 2, Step 3: 实现并验证

Run: `uv run pytest services/risk/tests -v`

Expected: PASS。

### Task 2, Step 4: 提交

```bash
git add services/risk uv.lock
git commit -m "feat: add deterministic risk authorization service"
```

## Task 3: KMS 信封加密领域

**Files:**

- Create: `services/kms-adapter/`
- Create: `services/kms-adapter/src/kms_adapter/models.py`
- Create: `services/kms-adapter/src/kms_adapter/provider.py`
- Create: `services/kms-adapter/src/kms_adapter/service.py`
- Create: `services/kms-adapter/tests/test_envelope_service.py`
- Create: `services/kms-adapter/migrations/versions/0001_kms_secrets.py`

### Task 3, Step 1: 写失败测试

验证 AES-GCM 随机 Nonce、加密上下文、密文不可读、跨租户拒绝、篡改拒绝、删除后
不可恢复和事务失败清理。

### Task 3, Step 2: 确认测试失败

Run: `uv run pytest services/kms-adapter/tests/test_envelope_service.py -v`

Expected: FAIL。

### Task 3, Step 3: 实现

明文数据密钥只存在于函数局部变量。数据库保存 `encrypted_data_key`、
`nonce`、`ciphertext` 和规范化加密上下文。

### Task 3, Step 4: 验证

Run: `uv run pytest services/kms-adapter/tests/test_envelope_service.py -v`

Expected: PASS。

## Task 4: 火山 KMS Provider 和 Broker API

**Files:**

- Create: `services/kms-adapter/src/kms_adapter/volcengine_provider.py`
- Create: `services/kms-adapter/src/kms_adapter/api.py`
- Create: `services/kms-adapter/src/kms_adapter/main.py`
- Create: `services/kms-adapter/tests/test_volcengine_provider.py`
- Create: `services/kms-adapter/tests/test_api.py`

### Task 4, Step 1: 写失败测试

使用 Mock HTTP/SDK 验证 `GenerateDataKey`、`Decrypt`、32 字节数据密钥、完全一致
的 EncryptionContext、服务令牌认证，以及云错误不泄漏 AK/SK。

### Task 4, Step 2: 确认测试失败

Run:

```bash
uv run pytest \
  services/kms-adapter/tests/test_volcengine_provider.py \
  services/kms-adapter/tests/test_api.py -v
```

Expected: FAIL。

### Task 4, Step 3: 实现并验证

Run: `uv run pytest services/kms-adapter/tests -v`

Expected: PASS。

### Task 4, Step 4: 提交

```bash
git add services/kms-adapter uv.lock
git commit -m "feat: add volcengine kms envelope adapter"
```

## Task 5: Trading 集成和全量验收

**Files:**

- Modify: `services/trading/src/trading/risk.py`
- Modify: `services/trading/src/trading/secrets.py`
- Modify: `services/trading/src/trading/config.py`
- Modify: `services/trading/tests/`
- Modify: `docs/integrations/binance-production-readiness.md`
- Modify: `docs/requirements/requirements-traceability-matrix.md`

### Task 5, Step 1: 写失败契约测试

验证 Trading 携带独立 KMS/Risk 服务令牌、KMS 请求包含租户、Risk 服务异常失败
关闭，审批令牌不能重放。

### Task 5, Step 2: 实现集成

KMS `resolve/delete` 请求增加 `tenant_id`。Risk 请求增加 `X-Service-Token`。
生产配置缺少任一服务令牌时拒绝启动。

### Task 5, Step 3: 全量验证

Run:

```bash
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy services/risk/src services/kms-adapter/src services/trading/src
uv run bandit -r services/risk/src services/kms-adapter/src services/trading/src
pnpm lint
pnpm test
pnpm build
```

Expected: 全部 PASS。

### Task 5, Step 4: 更新文档与提交

真实火山 KMS、Risk 策略 UAT、固定出口和生产帐号验证继续保持 `Blocked`，不得用
Mock 结果替代生产验收。

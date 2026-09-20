# Binance NautilusTrader Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将币安接入迁移为 NautilusTrader 驱动的现货与 U 本位单活动帐号
方案，并支持登录后添加、加密保存和切换帐号。

**Architecture:** 保留单个 FastAPI Trading Service，在进程内托管一个
Nautilus `LiveNode`，分别注册 Spot 与 USD-M 客户端。凭据由本地主密钥使用
AES-256-GCM 加密入库，业务层仅保留帐号生命周期、薄执行适配、本地风控和
只读投影。

**Tech Stack:** Python 3.12、NautilusTrader 1.231.0、FastAPI、SQLAlchemy、
MySQL、cryptography、React 19、Vitest、pytest、Docker Compose。

---

## 实施约束

- 使用 @bits-unit-test-gen 维护单元测试。
- 前端完成后使用 @webapp-testing 验证登录、帐号添加和切换。
- 每个任务通过测试后独立提交，不把删除旧代码和新运行时引入放在同一提交。
- 生产真实下单必须等 Testnet、网络和权限准入全部通过。
- 不实现现货全仓/逐仓杠杆、借还款、币本位、期权和多帐号并行。

### Task 1: NautilusTrader 依赖 POC

**Files:**

- Modify: `services/trading/pyproject.toml`
- Modify: `uv.lock`
- Create: `services/trading/src/trading/binance_runtime/__init__.py`
- Create: `services/trading/src/trading/binance_runtime/config.py`
- Create: `services/trading/tests/test_nautilus_config.py`

**Step 1:** 写失败测试

验证配置可以生成两个不同客户端：

```python
def test_builds_distinct_spot_and_futures_clients():
    configs = build_binance_client_configs(testnet=True)
    assert configs.spot.client_id == "BINANCE_SPOT"
    assert configs.futures.client_id == "BINANCE_FUTURES"
```

同时验证：

- Spot 使用 `BinanceProductType.SPOT`。
- Futures 使用 `BinanceProductType.USD_M`。
- 未提供凭据时只能创建数据客户端。
- 生产环境不会误用 Testnet URL。

**Step 2:** 运行并确认失败

```bash
uv run pytest services/trading/tests/test_nautilus_config.py -v
```

Expected: FAIL，`trading.binance_runtime` 尚不存在。

**Step 3:** 添加并锁定依赖

在 `services/trading/pyproject.toml` 添加：

```toml
"nautilus_trader==1.231.0",
```

运行：

```bash
uv lock
uv sync --package trading
```

确认当前 Linux/CPU 和 Python 3.12 使用预编译 wheel。

**Step 4:** 实现最小配置构造器

仅使用 Nautilus 公共 API；不导入 `nautilus_trader.adapters.binance` 的私有
HTTP/WebSocket 模块。

**Step 5:** 验证

```bash
uv run pytest services/trading/tests/test_nautilus_config.py -v
uv run python -c "import nautilus_trader; print(nautilus_trader.__version__)"
```

Expected: 测试通过，版本输出 `1.231.0`。

**Step 6:** 提交

```bash
git add services/trading/pyproject.toml uv.lock \
  services/trading/src/trading/binance_runtime \
  services/trading/tests/test_nautilus_config.py
git commit -m "build: add pinned nautilustrader runtime"
```

### Task 2: 本地凭据加密

**Files:**

- Modify: `services/trading/src/trading/config.py`
- Modify: `services/trading/src/trading/secrets.py`
- Modify: `services/trading/src/trading/models.py`
- Create: `services/trading/migrations/versions/0003_local_binance_credentials.py`
- Modify: `services/trading/tests/test_security.py`
- Modify: `services/trading/tests/test_config.py`

**Step 1:** 写失败测试

覆盖：

- 主密钥文件缺失、非普通文件或权限宽于 `600` 时拒绝启动。
- 同一明文两次加密得到不同 nonce 和密文。
- 修改 `account_id`、版本或密文后认证失败。
- API 响应、异常和 `repr` 不包含明文。

关键接口：

```python
class LocalCredentialVault:
    def encrypt(
        self, account_id: str, value: dict[str, str]
    ) -> EncryptedCredential: ...

    def decrypt(
        self, account_id: str, record: EncryptedCredential
    ) -> dict[str, str]: ...
```

**Step 2:** 运行并确认失败

```bash
uv run pytest \
  services/trading/tests/test_security.py \
  services/trading/tests/test_config.py -v
```

Expected: FAIL，当前生产配置强制 KMS，且本地后端使用 Fernet 单字段存储。

**Step 3:** 实现迁移和 Vault

- 增加 `credential_ciphertext`、`credential_nonce`、`credential_version`。
- 使用 `AESGCM`，附加认证数据包含 `account_id` 和凭据类型。
- 配置改为 `BINANCE_CREDENTIAL_MASTER_KEY_FILE`。
- 删除 Trading Service 对 `KMS_URL`、`KMS_SERVICE_TOKEN` 的生产要求。

**Step 4:** 验证

```bash
uv run pytest \
  services/trading/tests/test_security.py \
  services/trading/tests/test_config.py -v
uv run bandit -r services/trading/src
```

Expected: 全部通过，无明文凭据告警。

**Step 5:** 提交

```bash
git add services/trading
git commit -m "feat: encrypt binance credentials locally"
```

### Task 3: 帐号领域收敛

**Files:**

- Modify: `services/trading/src/trading/models.py`
- Modify: `services/trading/src/trading/accounts.py`
- Modify: `services/trading/src/trading/api/accounts.py`
- Modify: `services/trading/tests/test_accounts.py`
- Modify: `services/trading/tests/test_api.py`
- Modify: `packages/contracts/proto/trading/v1/trading.proto`

**Step 1:** 写失败测试

验证：

- 只允许 `hmac|ed25519`。
- 产品固定为 `spot|usdm_futures`。
- 可保存多个帐号，但仅一个 `active`。
- 激活第二个帐号时第一个帐号变为 `ready`。
- 活动帐号或存在未决订单的帐号不能直接删除。
- 保存人工确认人和确认时间。

**Step 2:** 运行并确认失败

```bash
uv run pytest \
  services/trading/tests/test_accounts.py \
  services/trading/tests/test_api.py -v
```

Expected: FAIL，当前模型仍包含 RSA、Margin Scope 和 KMS 引用。

**Step 3:** 实现最小帐号 API

```text
GET    /api/v1/trading/binance/accounts
POST   /api/v1/trading/binance/accounts
PUT    /api/v1/trading/binance/accounts/{id}
DELETE /api/v1/trading/binance/accounts/{id}
POST   /api/v1/trading/binance/accounts/{id}/test
POST   /api/v1/trading/binance/accounts/{id}/activate
POST   /api/v1/trading/binance/accounts/active/deactivate
```

帐号写操作继续要求管理员和近期 MFA。

**Step 4:** 验证

```bash
uv run pytest \
  services/trading/tests/test_accounts.py \
  services/trading/tests/test_api.py -v
```

Expected: PASS。

**Step 5:** 提交

```bash
git add services/trading packages/contracts
git commit -m "feat: simplify binance account lifecycle"
```

### Task 4: Nautilus Runtime Manager

**Files:**

- Create: `services/trading/src/trading/binance_runtime/manager.py`
- Create: `services/trading/src/trading/binance_runtime/events.py`
- Create: `services/trading/src/trading/binance_runtime/ports.py`
- Create: `services/trading/tests/test_runtime_manager.py`
- Modify: `services/trading/src/trading/main.py`
- Modify: `services/trading/src/trading/api/health.py`

**Step 1:** 写失败测试

使用 Fake Node 覆盖：

- 只允许一个节点运行。
- 激活时先停止旧节点，再启动新节点。
- 启动对账完成前 `accepting_orders=false`。
- Spot 或 Futures 单侧失联只冻结对应产品。
- 停止后凭据引用被清除。

定义可替换端口：

```python
class TradingNode(Protocol):
    async def start(self) -> None: ...
    async def reconcile(self) -> ReconciliationResult: ...
    async def stop(self) -> None: ...
```

**Step 2:** 运行并确认失败

```bash
uv run pytest services/trading/tests/test_runtime_manager.py -v
```

Expected: FAIL，Runtime Manager 尚不存在。

**Step 3:** 实现生命周期

- 在 FastAPI lifespan 中启动管理器。
- 服务启动时读取活动帐号。
- 无活动帐号时健康但不 ready for trading。
- 使用异步锁串行化 activate/deactivate。

**Step 4:** 验证

```bash
uv run pytest \
  services/trading/tests/test_runtime_manager.py \
  services/trading/tests/test_health.py -v
```

Expected: PASS。

**Step 5:** 提交

```bash
git add services/trading
git commit -m "feat: manage nautilus binance runtime"
```

### Task 5: 账户、订单和持仓投影

**Files:**

- Create: `services/trading/src/trading/binance_runtime/projections.py`
- Create: `services/trading/src/trading/api/binance_portfolio.py`
- Create: `services/trading/tests/test_binance_projections.py`
- Modify: `services/trading/src/trading/main.py`
- Modify: `services/trading/src/trading/models.py`

**Step 1:** 写失败测试

覆盖 Nautilus 事件到平台投影：

- Spot 与 Futures 余额不串产品。
- 外部手工订单标记 `source=external`。
- 重复成交 ID 只入库一次。
- 数据超时后标记 `stale`。
- 重启对账覆盖旧快照并保留平台订单关联。

**Step 2:** 运行并确认失败

```bash
uv run pytest services/trading/tests/test_binance_projections.py -v
```

Expected: FAIL，投影模块不存在。

**Step 3:** 实现只读接口

```text
GET /api/v1/trading/binance/status
GET /api/v1/trading/binance/balances
GET /api/v1/trading/binance/positions
GET /api/v1/trading/binance/orders
```

**Step 4:** 验证并提交

```bash
uv run pytest services/trading/tests/test_binance_projections.py -v
git add services/trading
git commit -m "feat: project nautilus account state"
```

### Task 6: 本地风控与订单执行

**Files:**

- Modify: `services/trading/src/trading/orders.py`
- Replace: `services/trading/src/trading/risk.py`
- Modify: `services/trading/src/trading/api/orders.py`
- Modify: `services/trading/tests/test_orders.py`
- Create: `services/trading/tests/test_local_risk_guard.py`

**Step 1:** 写失败测试

覆盖：

- 无活动帐号、未对账、数据过期和急停拒绝。
- 最大单笔金额、仓位、杠杆和每日亏损限制。
- 相同幂等键同请求返回原订单，不同请求返回冲突。
- Nautilus 明确拒绝映射为 `rejected`。
- 不确定提交保持 `pending_reconciliation`，不再次调用节点。

**Step 2:** 运行并确认失败

```bash
uv run pytest \
  services/trading/tests/test_orders.py \
  services/trading/tests/test_local_risk_guard.py -v
```

**Step 3:** 删除远程 Risk 调用并适配 Nautilus 命令

`POST /orders` 不再要求 `X-Risk-Approval`，但继续要求 `Idempotency-Key`。
所有 Decimal 校验在转换为 Nautilus Quantity/Price 前完成。

**Step 4:** 验证并提交

```bash
uv run pytest \
  services/trading/tests/test_orders.py \
  services/trading/tests/test_local_risk_guard.py -v
git add services/trading
git commit -m "feat: route orders through nautilus"
```

### Task 7: U 本位杠杆与保证金模式

**Files:**

- Create: `services/trading/src/trading/api/binance_futures.py`
- Modify: `services/trading/src/trading/binance_runtime/manager.py`
- Create: `services/trading/tests/test_binance_futures.py`
- Modify: `services/trading/src/trading/main.py`

**Step 1:** 写失败测试

验证：

- 杠杆范围受本地最大值约束。
- 设置保证金模式只允许 `cross|isolated`。
- 未完成对账、非 Futures instrument、连接断开时拒绝。
- 交易所返回“无需变更”按幂等成功处理。
- 设置失败不修改本地已确认状态。

**Step 2:** 运行并确认失败

```bash
uv run pytest services/trading/tests/test_binance_futures.py -v
```

**Step 3:** 实现接口

```text
PUT /api/v1/trading/binance/futures/{symbol}/leverage
PUT /api/v1/trading/binance/futures/{symbol}/margin-mode
```

**Step 4:** 验证并提交

```bash
uv run pytest services/trading/tests/test_binance_futures.py -v
git add services/trading
git commit -m "feat: manage usdm leverage and margin mode"
```

### Task 8: Web 帐号管理与交易工作区

**Files:**

- Modify: `apps/web/src/features/trading/types.ts`
- Modify: `apps/web/src/features/trading/api.ts`
- Modify: `apps/web/src/features/trading/AccountBindingDialog.tsx`
- Modify: `apps/web/src/features/trading/AccountBindingDialog.test.tsx`
- Modify: `apps/web/src/pages/trading/TradingWorkspace.tsx`
- Modify: `apps/web/src/features/trading/TradingWorkspace.test.tsx`
- Modify: `apps/web/src/pages/trading/BinanceTradingPage.tsx`

**Step 1:** 写失败测试

验证：

- 未登录不能进入交易页面。
- 币安页可添加 HMAC/Ed25519 帐号。
- 不再显示 RSA、全仓杠杆、逐仓杠杆 Scope。
- 保存后敏感字段离开 DOM。
- 多帐号列表只能有一个“当前”标记。
- 切换中禁用交易控件。
- Spot 与 U 本位标签展示对应余额、订单和持仓。

**Step 2:** 运行并确认失败

```bash
pnpm --filter web test -- \
  AccountBindingDialog.test.tsx \
  TradingWorkspace.test.tsx
```

**Step 3:** 实现最小交互

删除 Scope 选择，改为固定能力说明；增加禁止提现确认、帐号测试、启用、停用和
删除操作。敏感字段继续使用受控状态并在所有退出路径清空。

**Step 4:** 验证

```bash
pnpm --filter web lint
pnpm --filter web test
pnpm --filter web build
```

**Step 5:** 浏览器验收

使用 @webapp-testing 在 1280x720 和 390x664 验证登录、帐号添加、切换、错误提示、
产品标签和无文本重叠。

**Step 6:** 提交

```bash
git add apps/web
git commit -m "feat: simplify binance account workspace"
```

### Task 9: 部署编排

**Files:**

- Modify: `services/trading/Dockerfile`
- Modify: `services/trading/.env.example`
- Modify: `infra/compose/docker-compose.deploy.yml`
- Modify: `infra/compose/.env.deploy.example`
- Modify: `scripts/deploy.sh`
- Modify: `scripts/tests/test_deployment_files.py`

**Step 1:** 写失败测试

验证：

- `binance-trading` Profile 只启动 Trading，不依赖 KMS/Risk。
- 主密钥文件以只读方式挂载。
- 主密钥权限不是 `600` 时启动脚本失败。
- 固定出口和 HTTPS 未确认时生产交易 Profile 拒绝启动。

**Step 2:** 运行并确认失败

```bash
uv run pytest scripts/tests/test_deployment_files.py -v
```

**Step 3:** 实现

- 将 `binance-readonly` 重命名为 `binance-trading`。
- 从 Profile 删除 `kms-adapter`、`risk` 和对应迁移任务。
- `deploy.sh init` 生成 32 字节主密钥文件，不写入 `.env.deploy`。
- Trading 容器只读挂载该文件。

**Step 4:** 验证

```bash
uv run pytest scripts/tests/test_deployment_files.py -v
docker compose \
  --env-file infra/compose/.env.deploy.example \
  -f infra/compose/docker-compose.yml \
  -f infra/compose/docker-compose.deploy.yml \
  --profile binance-trading config --quiet
```

**Step 5:** 提交

```bash
git add services/trading infra/compose scripts
git commit -m "ops: simplify binance trading deployment"
```

### Task 10: 删除旧币安实现

**Files:**

- Delete: `services/trading/src/trading/binance/client.py`
- Delete: `services/trading/src/trading/binance/signing.py`
- Delete: `services/trading/tests/test_binance_client.py`
- Delete: `services/trading/tests/test_binance_signing.py`
- Modify: `services/trading/src/trading/binance/__init__.py`
- Modify: `services/trading/src/trading/api/dependencies.py`
- Modify: `services/trading/tests/test_internal_service_clients.py`

**Step 1:** 添加架构守卫测试

测试源码不得：

- 导入旧 `BinanceClient` 或 `BinanceSigner`。
- 配置 `KMS_URL`、`RISK_SERVICE_URL` 或 `X-Risk-Approval`。
- 包含 `cross_margin`、`isolated_margin`、`margin-loans` 和
  `margin-repayments` 的活动路由。

**Step 2:** 删除旧实现并修复导入

先删除调用点，再删除文件；不得保留未使用的兼容层。

**Step 3:** 验证

```bash
uv run pytest services/trading/tests -v
uv run ruff check services/trading
uv run mypy services/trading/src
```

Expected: 全部通过，无旧类型引用。

**Step 4:** 提交

```bash
git add services/trading
git commit -m "refactor: remove custom binance connector"
```

### Task 11: Testnet 集成与故障演练

**Files:**

- Create: `tests/integration/binance/conftest.py`
- Create: `tests/integration/binance/test_spot_lifecycle.py`
- Create: `tests/integration/binance/test_usdm_lifecycle.py`
- Create: `tests/integration/binance/test_recovery.py`
- Create: `tests/integration/binance/README.md`

**Step 1:** 建立显式门禁

没有 `BINANCE_TESTNET_ENABLED=true` 和独立 Testnet 凭据时全部跳过，不得回退生产。

**Step 2:** 实现生命周期用例

- Spot 限价下单、查询、撤单。
- USD-M 低杠杆、逐仓模式、下单、撤单和减仓。
- WebSocket 中断、进程重启和恢复对账。

**Step 3:** 执行

```bash
BINANCE_TESTNET_ENABLED=true \
uv run pytest tests/integration/binance -v
```

Expected: 全部通过，清理测试订单和仓位。

**Step 4:** 提交

```bash
git add tests/integration/binance
git commit -m "test: cover binance nautilus integration"
```

### Task 12: 全量验证与文档收口

**Files:**

- Modify: `docs/integrations/binance-production-readiness.md`
- Modify: `docs/requirements/requirements-traceability-matrix.md`
- Modify: `docs/testing/test-cases.md`
- Modify: `docs/testing/acceptance-plan.md`
- Modify: `services/trading/README.md`

**Step 1:** 运行全量自动化

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy services/trading/src
uv run pytest
uv run bandit -r services/trading/src
pnpm lint
pnpm test
pnpm build
git diff --check
```

Expected: 全部通过。

**Step 2:** 检查敏感信息和旧架构残留

```bash
rg -n "api[_-]?key|private[_-]?key|secret" services/trading apps/web
rg -n "BinanceClient|BinanceSigner|cross_margin|isolated_margin" \
  services/trading apps/web infra/compose scripts
rg -n "KMS_URL|RISK_SERVICE_URL" \
  services/trading apps/web infra/compose scripts
```

Expected: 第一条仅出现受控字段和测试数据；第二条无活动实现引用。

**Step 3:** 更新验收状态

仅将有自动化证据的项目标记为 Implemented。Testnet、生产网络、真实帐号和真实资金
未通过前必须保持 Blocked。

**Step 4:** 最终提交

```bash
git add docs services/trading/README.md
git commit -m "docs: align binance nautilus delivery status"
```

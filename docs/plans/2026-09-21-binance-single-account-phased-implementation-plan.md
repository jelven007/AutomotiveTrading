# Binance Single-Account Phased Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement
> this plan task-by-task.

**Goal:** 在现有 Trading Service 中交付单币安账号的只读查询，并在同一
Nautilus Runtime 上分阶段增加人工下单、撤单、杠杆和保证金模式。

**Architecture:** 复用现有 FastAPI、MySQL、AES-256-GCM 和 NautilusTrader
1.231.0。阶段一只提供单账号替换及聚合账户查询；阶段二增加受 MFA、运行时状态
和幂等记录保护的人工交易写接口。

**Tech Stack:** Python 3.12、NautilusTrader 1.231.0、FastAPI、SQLAlchemy、
MySQL、cryptography、React 19、TypeScript、Vitest、pytest、Docker Compose。

---

<!-- markdownlint-disable MD024 -->

## 实施约束

- 使用 @bits-unit-test-gen 维护单元测试。
- 前端完成后使用 @webapp-testing 验证桌面和移动视口。
- 每个任务先写失败测试，再写最小实现并独立提交。
- 不修改 A 股、港美或其他交易通道的行为。
- 阶段一完成并部署前，不开始阶段二。
- 阶段二通过 Testnet 前，生产 `LIVE_TRADING_ENABLED` 必须保持 `false`。
- 当前工作区存在未提交改动，实施时只暂存本任务涉及的文件。

## 阶段一：单账号只读

### Task 1: 定义单账号 API 契约

**Files:**

- Create: `services/trading/src/trading/binance_account.py`
- Create: `services/trading/src/trading/api/binance_account.py`
- Create: `services/trading/tests/test_binance_account.py`
- Modify: `services/trading/src/trading/main.py`
- Modify: `services/trading/src/trading/accounts.py`

#### Step 1: 写失败测试

覆盖：

- 未绑定时 `GET /api/v1/trading/binance/account` 返回 404。
- `PUT /api/v1/trading/binance/account` 只接受别名、Key、Secret 和 IP 确认。
- 第二次 `PUT` 覆盖原账号，不增加记录数。
- 请求和响应不包含 `credential_type`、Scope、`is_active` 或 `trading_enabled`。
- 旧的币安 activate/deactivate 路径返回 404。

目标请求模型：

```python
class BinanceAccountReplaceCommand(BaseModel):
    alias: str = Field(min_length=1, max_length=120)
    api_key: SecretStr
    api_secret: SecretStr
    ip_whitelist_confirmed: bool
```

#### Step 2: 运行并确认失败

```bash
uv run pytest services/trading/tests/test_binance_account.py -v
```

Expected: FAIL，新路由和服务尚不存在。

#### Step 3: 实现最小查询和替换接口

新增：

```text
GET    /api/v1/trading/binance/account
PUT    /api/v1/trading/binance/account
DELETE /api/v1/trading/binance/account
```

保留现有通用交易账号 API 供其他市场使用，但拒绝通过旧路径创建、激活或切换
Binance 账号。

#### Step 4: 验证

```bash
uv run pytest \
  services/trading/tests/test_binance_account.py \
  services/trading/tests/test_accounts.py \
  services/trading/tests/test_api.py -v
```

Expected: 新契约通过，非 Binance 账号测试不回归。

#### Step 5: 提交

```bash
git add services/trading/src/trading/binance_account.py \
  services/trading/src/trading/api/binance_account.py \
  services/trading/src/trading/main.py \
  services/trading/src/trading/accounts.py \
  services/trading/tests/test_binance_account.py
git commit -m "feat: add single binance account contract"
```

### Task 2: 收敛数据库单账号约束

**Files:**

- Modify: `services/trading/src/trading/models.py`
- Create: `services/trading/migrations/versions/0004_single_binance_account.py`
- Create: `services/trading/tests/test_single_binance_migration.py`
- Modify: `services/trading/tests/test_accounts.py`

#### Step 1: 写失败测试

验证：

- 同一 `tenant_id` 不能写入第二条 `provider=binance` 记录。
- 不同用户可以各保存一条 Binance 记录。
- 迁移发现已有重复 Binance 记录时明确失败，不静默删除凭据。
- HMAC 是新接口唯一接受的币安凭据类型。

物理表继续复用 `trading_accounts`，避免为同一概念新建重复表；增加等价于以下
约束的数据库索引：

```text
UNIQUE(tenant_id, provider) WHERE provider = 'binance'
```

MySQL 不支持部分唯一索引时，增加只对 Binance 写入的固定
`account_slot='primary'` 字段，并建立：

```text
UNIQUE(tenant_id, provider, account_slot)
```

#### Step 2: 运行并确认失败

```bash
uv run pytest services/trading/tests/test_single_binance_migration.py -v
```

#### Step 3: 实现迁移和模型约束

- 不删除其他市场的多账号能力。
- 不迁移或复制明文凭据。
- 删除 Binance 新流程对 `TradingAccountScope` 和 `is_active` 的依赖。

#### Step 4: 验证

```bash
uv run pytest \
  services/trading/tests/test_single_binance_migration.py \
  services/trading/tests/test_accounts.py -v
uv run alembic -c services/trading/alembic.ini upgrade head
```

Expected: 迁移通过，单账号唯一约束生效。

#### Step 5: 提交

```bash
git add services/trading/src/trading/models.py \
  services/trading/migrations/versions/0004_single_binance_account.py \
  services/trading/tests/test_single_binance_migration.py \
  services/trading/tests/test_accounts.py
git commit -m "feat: enforce one binance account per user"
```

### Task 3: 实现安全的候选账号验证与原子替换

**Files:**

- Modify: `services/trading/src/trading/binance_account.py`
- Modify: `services/trading/src/trading/secrets.py`
- Create: `services/trading/src/trading/binance_runtime/manager.py`
- Create: `services/trading/src/trading/binance_runtime/ports.py`
- Create: `services/trading/tests/test_binance_account_replacement.py`
- Create: `services/trading/tests/test_binance_runtime_manager.py`

#### Step 1: 写失败测试

覆盖：

- 权限探测失败时不写数据库、不删除旧密文。
- 候选 Runtime 启动或读取任一区域失败时不切换。
- 成功时同一事务更新账号和新密文，事务提交后删除旧密文。
- Runtime 切换失败时回滚数据库并保留旧 Runtime。
- 新凭据从异常、`repr` 和日志中消失。

定义可测试端口：

```python
class CandidateRuntime(Protocol):
    async def validate(self) -> "BinanceOverview": ...
    async def stop(self) -> None: ...


class RuntimeManager(Protocol):
    async def build_candidate(
        self, api_key: str, api_secret: str
    ) -> CandidateRuntime: ...
    async def replace(self, candidate: CandidateRuntime) -> None: ...
```

#### Step 2: 运行并确认失败

```bash
uv run pytest \
  services/trading/tests/test_binance_account_replacement.py \
  services/trading/tests/test_binance_runtime_manager.py -v
```

#### Step 3: 实现替换顺序

严格执行：

1. 最小权限探测。
2. 启动候选 Runtime。
3. 获取 Spot、USD-M 余额和持仓。
4. 写入新密文和账号摘要。
5. 提交事务。
6. 切换 Runtime。
7. 删除旧密文。

任一步失败都停止候选 Runtime，并保留旧状态。

#### Step 4: 验证并提交

```bash
uv run pytest \
  services/trading/tests/test_binance_account_replacement.py \
  services/trading/tests/test_binance_runtime_manager.py \
  services/trading/tests/test_security.py -v
git add services/trading
git commit -m "feat: replace binance account atomically"
```

### Task 4: 限制权限探测客户端

**Files:**

- Modify: `services/trading/src/trading/binance/client.py`
- Modify: `services/trading/src/trading/binance/signing.py`
- Replace: `services/trading/tests/test_binance_client.py`
- Modify: `services/trading/tests/test_binance_signing.py`

#### Step 1: 写失败测试

验证权限探测客户端：

- 只能请求 `/sapi/v1/account/apiRestrictions`。
- 拒绝非 GET 方法和其他路径。
- 要求 `enableReading=true`、`ipRestrict=true`。
- 要求提现、内部划转和通用划转均为 false。
- 返回现货和 U 本位交易权限，但阶段一不使用其执行能力。

#### Step 2: 运行并确认失败

```bash
uv run pytest \
  services/trading/tests/test_binance_client.py \
  services/trading/tests/test_binance_signing.py -v
```

#### Step 3: 删除写入能力

从 `BinanceClient` 删除订单、撤单、借还款、杠杆、保证金和通用
`signed_request` 公共入口，将其重命名为 `BinancePermissionProbe`。

#### Step 4: 验证并提交

```bash
uv run pytest services/trading/tests/test_binance_client.py -v
rg -n "submit_order|cancel_order|margin-loans|margin-repayments" \
  services/trading/src/trading/binance
git add services/trading/src/trading/binance \
  services/trading/tests/test_binance_client.py \
  services/trading/tests/test_binance_signing.py
git commit -m "refactor: restrict binance rest client to permissions"
```

Expected: `rg` 不返回活动实现。

### Task 5: 实现 Nautilus 聚合账户查询

**Files:**

- Create: `services/trading/src/trading/binance_runtime/overview.py`
- Create: `services/trading/src/trading/api/binance_overview.py`
- Create: `services/trading/tests/test_binance_overview.py`
- Modify: `services/trading/src/trading/binance_runtime/manager.py`
- Modify: `services/trading/src/trading/main.py`

#### Step 1: 写失败测试

覆盖：

- 未绑定账号返回 `binance.account_missing`。
- 现货仅返回非零余额。
- U 本位返回余额和非零持仓。
- Spot 失败时 USD-M 和权限仍返回。
- USD-M 失败时 Spot 和权限仍返回。
- 5 秒内普通请求复用快照。
- `refresh=true` 绕过快照。
- 查询不写数据库。

区域模型：

```python
class OverviewSection[T](BaseModel):
    status: Literal["ok", "error"]
    data: T | None
    error: ProblemSummary | None = None
```

#### Step 2: 运行并确认失败

```bash
uv run pytest services/trading/tests/test_binance_overview.py -v
```

#### Step 3: 实现接口

```text
GET /api/v1/trading/binance/overview
GET /api/v1/trading/binance/overview?refresh=true
```

不要创建后台任务、Redis Key、余额表或持仓表。

#### Step 4: 验证并提交

```bash
uv run pytest \
  services/trading/tests/test_binance_overview.py \
  services/trading/tests/test_health.py -v
git add services/trading
git commit -m "feat: query binance account overview"
```

### Task 6: 重做币安单账号页面

**Files:**

- Modify: `apps/web/src/features/trading/types.ts`
- Modify: `apps/web/src/features/trading/api.ts`
- Modify: `apps/web/src/features/trading/AccountBindingDialog.tsx`
- Modify: `apps/web/src/features/trading/AccountBindingDialog.test.tsx`
- Create: `apps/web/src/features/trading/BinanceAccountOverview.tsx`
- Create: `apps/web/src/features/trading/BinanceAccountOverview.test.tsx`
- Modify: `apps/web/src/pages/trading/BinanceTradingPage.tsx`
- Modify: `apps/web/src/features/trading/TradingWorkspace.test.tsx`
- Modify: `apps/web/src/styles/tokens.css`

#### Step 1: 写失败测试

验证：

- 未绑定时只显示“添加账号”。
- 表单只有别名、API Key、API Secret 和 IP 确认。
- 绑定后只有“刷新”“重新绑定”和“删除账号”。
- 不显示账号数量、当前账号、激活、停用、急停或 Scope。
- 三个标签为“现货资产”“U 本位”“API 权限”。
- Spot/USD-M 局部错误不隐藏成功区域。
- 所有退出路径清空敏感字段。

#### Step 2: 运行并确认失败

```bash
pnpm --filter web test -- \
  AccountBindingDialog.test.tsx \
  BinanceAccountOverview.test.tsx \
  TradingWorkspace.test.tsx
```

#### Step 3: 实现最小页面

删除 Binance 页面对通用多账号 `TradingWorkspace` 的依赖。其他市场继续复用
原组件。

#### Step 4: 验证

```bash
pnpm --filter web lint
pnpm --filter web test
pnpm --filter web build
```

#### Step 5: 浏览器验收

使用 @webapp-testing 在 `1280x720` 和 `390x664` 验证：

- 未绑定、已绑定、加载、局部失败和空资产状态。
- 弹窗无溢出，长资产名和错误信息不遮挡控件。
- 页面没有交易按钮。

#### Step 6: 提交

```bash
git add apps/web/src/features/trading \
  apps/web/src/pages/trading/BinanceTradingPage.tsx \
  apps/web/src/styles/tokens.css
git commit -m "feat: simplify binance account page"
```

### Task 7: 阶段一部署与真实只读验收

**Files:**

- Modify: `services/trading/.env.example`
- Modify: `infra/compose/docker-compose.deploy.yml`
- Modify: `scripts/deploy.sh`
- Modify: `scripts/tests/test_deployment_files.py`
- Create: `tests/integration/binance/test_read_only_overview.py`
- Modify: `docs/operations/binance-nautilustrader-runbook.md`

#### Step 1: 写失败测试

验证：

- 主密钥只读挂载且宿主机权限为 `600`。
- `FIXED_EGRESS_IP_CONFIGURED=true` 才允许绑定。
- `LIVE_TRADING_ENABLED=false` 时交易路由不存在或返回关闭状态。
- 未显式提供生产测试凭据时真实集成测试跳过。

#### Step 2: 运行并确认失败

```bash
uv run pytest \
  scripts/tests/test_deployment_files.py \
  tests/integration/binance/test_read_only_overview.py -v
```

#### Step 3: 实现部署调整

- 保留 Trading 和 Nautilus 依赖。
- 不启动 Risk、KMS、Kafka 或独立 Binance Connector。
- 健康检查分别报告 API、Spot 和 USD-M 状态。

#### Step 4: 执行生产只读验收

```bash
uv run pytest
pnpm --filter web test
pnpm --filter web build
```

部署后验证：

```text
GET /api/v1/trading/binance/account
GET /api/v1/trading/binance/overview?refresh=true
```

Expected: 权限、现货余额、U 本位余额和非零持仓与币安一致。

#### Step 5: 提交

```bash
git add services/trading/.env.example infra/compose scripts \
  tests/integration/binance/test_read_only_overview.py \
  docs/operations/binance-nautilustrader-runbook.md
git commit -m "ops: deploy binance read-only account flow"
```

## 阶段二：人工交易

### Task 8: 增加 MFA 交易会话与写入总门禁

**Files:**

- Create: `services/trading/src/trading/trading_session.py`
- Create: `services/trading/tests/test_trading_session.py`
- Modify: `services/trading/src/trading/api/dependencies.py`
- Modify: `services/identity-tenant/src/identity_tenant/auth.py`
- Modify: `services/identity-tenant/tests/test_auth.py`

#### Step 1: 写失败测试

验证：

- 绑定和查询不要求 MFA。
- 完成 MFA 后获得最长 15 分钟的交易会话声明。
- 过期、缺失或用户不匹配时所有币安写操作返回
  `binance.trading_session_required`。
- `LIVE_TRADING_ENABLED=false` 时始终拒绝。

#### Step 2: 运行并确认失败

```bash
uv run pytest \
  services/trading/tests/test_trading_session.py \
  services/identity-tenant/tests/test_auth.py -v
```

#### Step 3: 实现统一依赖

```python
def require_binance_trading_session(
    principal: Principal,
    runtime: RuntimeGuard,
) -> None:
    ...
```

所有阶段二路由只调用该依赖，不重复实现 MFA 判断。

#### Step 4: 验证并提交

```bash
uv run pytest services/trading/tests services/identity-tenant/tests -v
git add services/trading services/identity-tenant
git commit -m "feat: gate binance writes with trading sessions"
```

### Task 9: 通过 Nautilus 实现下单与单笔撤单

**Files:**

- Create: `services/trading/src/trading/binance_orders.py`
- Create: `services/trading/src/trading/api/binance_orders.py`
- Create: `services/trading/tests/test_binance_orders.py`
- Modify: `services/trading/src/trading/binance_runtime/manager.py`
- Modify: `services/trading/src/trading/models.py`
- Create: `services/trading/migrations/versions/0005_binance_orders.py`
- Modify: `services/trading/src/trading/main.py`

#### Step 1: 写失败测试

覆盖：

- Spot/USD-M 市价和限价单映射。
- 自动策略来源拒绝。
- 相同幂等键和请求只提交一次。
- 相同幂等键不同请求返回 `idempotency.conflict`。
- 未就绪、状态过期和缺失交易权限时不调用 Nautilus。
- 明确拒绝保存为 `rejected`。
- 超时或断连保存为 `pending_reconciliation`，不重发。
- 单笔撤单使用独立幂等键。

#### Step 2: 运行并确认失败

```bash
uv run pytest services/trading/tests/test_binance_orders.py -v
```

#### Step 3: 实现最小接口

```text
GET  /api/v1/trading/binance/orders
POST /api/v1/trading/binance/orders
POST /api/v1/trading/binance/orders/{order_id}/cancel
```

下单 DTO：

```python
class BinanceOrderCommand(BaseModel):
    product: Literal["spot", "usdm_futures"]
    instrument_id: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"]
    quantity: Decimal = Field(gt=0)
    limit_price: Decimal | None = Field(default=None, gt=0)
    time_in_force: Literal["GTC"] | None = None
```

#### Step 4: 验证并提交

```bash
uv run pytest \
  services/trading/tests/test_binance_orders.py \
  services/trading/tests/test_binance_runtime_manager.py -v
git add services/trading
git commit -m "feat: execute manual binance orders with nautilus"
```

### Task 10: 增加 U 本位杠杆和保证金模式

**Files:**

- Create: `services/trading/src/trading/binance_futures.py`
- Create: `services/trading/src/trading/api/binance_futures.py`
- Create: `services/trading/tests/test_binance_futures.py`
- Modify: `services/trading/src/trading/binance_runtime/manager.py`
- Modify: `services/trading/src/trading/main.py`

#### Step 1: 写失败测试

验证：

- 杠杆只接受交易所 instrument 允许的范围。
- 保证金模式只接受 `cross|isolated`。
- 每个请求都要求独立 `Idempotency-Key`。
- 交易所返回“无需变更”时按幂等成功处理。
- 失败或超时时不伪造本地成功状态。
- 双向持仓模式请求返回 `feature.not_supported`。

#### Step 2: 运行并确认失败

```bash
uv run pytest services/trading/tests/test_binance_futures.py -v
```

#### Step 3: 实现接口

```text
PUT /api/v1/trading/binance/futures/{symbol}/leverage
PUT /api/v1/trading/binance/futures/{symbol}/margin-mode
```

#### Step 4: 验证并提交

```bash
uv run pytest services/trading/tests/test_binance_futures.py -v
git add services/trading
git commit -m "feat: manage binance futures settings"
```

### Task 11: 增加人工交易页面

**Files:**

- Create: `apps/web/src/features/trading/BinanceOrderTicket.tsx`
- Create: `apps/web/src/features/trading/BinanceOrderTicket.test.tsx`
- Create: `apps/web/src/features/trading/BinanceOrdersTable.tsx`
- Create: `apps/web/src/features/trading/BinanceOrdersTable.test.tsx`
- Create: `apps/web/src/features/trading/BinanceFuturesSettings.tsx`
- Create: `apps/web/src/features/trading/BinanceFuturesSettings.test.tsx`
- Modify: `apps/web/src/pages/trading/BinanceTradingPage.tsx`
- Modify: `apps/web/src/features/trading/api.ts`
- Modify: `apps/web/src/features/trading/types.ts`

#### Step 1: 写失败测试

验证：

- 功能开关关闭时不渲染交易区域。
- 无 MFA 交易会话时先打开身份验证。
- 订单确认区明确显示产品、方向、数量和价格。
- 提交期间禁用重复点击。
- 每次写操作生成独立幂等键。
- 撤单、杠杆和保证金模式显示交易所确认结果。
- `pending_reconciliation` 显示“待核对”，不提供重试按钮。

#### Step 2: 运行并确认失败

```bash
pnpm --filter web test -- \
  BinanceOrderTicket.test.tsx \
  BinanceOrdersTable.test.tsx \
  BinanceFuturesSettings.test.tsx
```

#### Step 3: 实现最小交易区

只提供市价、限价、单笔撤单、杠杆和保证金模式。不要加入条件单、批量撤单、
双向持仓或自动策略控件。

#### Step 4: 验证并提交

```bash
pnpm --filter web lint
pnpm --filter web test
pnpm --filter web build
git add apps/web
git commit -m "feat: add manual binance trading controls"
```

### Task 12: Testnet、故障演练和生产门禁

**Files:**

- Create: `tests/integration/binance/test_spot_orders.py`
- Create: `tests/integration/binance/test_usdm_orders.py`
- Create: `tests/integration/binance/test_reconciliation.py`
- Modify: `tests/integration/binance/README.md`
- Modify: `docs/integrations/binance-production-readiness.md`
- Modify: `docs/testing/results/README.md`

#### Step 1: 建立显式门禁

没有以下配置时全部 Skip，不得回退到生产：

```text
BINANCE_TESTNET_ENABLED=true
BINANCE_TESTNET_API_KEY=<secret>
BINANCE_TESTNET_SECRET=<secret>
```

#### Step 2: 执行生命周期

- Spot 市价、限价和撤单。
- USD-M 低杠杆、逐仓、下单和撤单。
- 写响应丢失、私有流中断和进程重启。

#### Step 3: 验证安全收敛

```bash
BINANCE_TESTNET_ENABLED=true \
uv run pytest tests/integration/binance -v
```

Expected:

- 无重复订单。
- 所有测试订单被撤销或明确成交。
- 未决订单可通过对账收敛。
- 日志和报告中无凭据。

#### Step 4: 全量验证

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

#### Step 5: 提交

```bash
git add tests/integration/binance docs
git commit -m "test: verify phased binance delivery"
```

## 执行顺序与发布门禁

| 里程碑 | 任务 | 退出条件 |
| --- | --- | --- |
| R1 | Task 1~4 | 单账号、安全替换和权限探测通过 |
| R2 | Task 5~7 | 真实只读查询上线，阶段一验收通过 |
| T1 | Task 8 | MFA 交易会话和写入总门禁通过 |
| T2 | Task 9~10 | Testnet 后端交易闭环通过 |
| T3 | Task 11 | 人工交易页面验收通过 |
| T4 | Task 12 | 故障演练和生产准入通过 |

任何阶段发现凭据泄漏、重复订单、旧账号被错误覆盖或
`pending_reconciliation` 无法收敛，必须停止进入下一阶段。

<!-- markdownlint-enable MD024 -->

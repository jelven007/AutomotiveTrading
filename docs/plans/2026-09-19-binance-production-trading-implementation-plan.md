# 币安生产交易 Implementation Plan

**Superseded（2026-09-21）：** 本计划已由
[`QT-PLAN-BIN-SIMPLE-001`](2026-09-21-binance-single-account-phased-implementation-plan.md)
取代，不得继续按本文实施。

> **For Claude:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 交付交易三市场工作台、生产帐号安全绑定，以及支持现货、全仓杠杆、逐仓杠杆和 U 本位永续的币安交易服务。

**Architecture:** 新建 FastAPI `trading` 服务，按帐号域、凭据提供器、风险闸门和
Binance Connector 分层。浏览器只提交一次凭据，服务只保存 KMS 引用和脱敏指纹；
生产写请求必须同时通过租户权限、近期 MFA、帐号 Scope、风控审批、幂等和全局急停。

**Tech Stack:** React 19、React Router、Vitest、FastAPI、Pydantic、SQLAlchemy、
Alembic、httpx、cryptography、pytest。

---

## 实施边界

- 一期支持 `spot`、`cross_margin`、`isolated_margin`、`usdm_futures`。
- 币安只使用生产 API 域名，不提供前端切换到测试网的入口。
- 本地开发可使用加密凭据后端；生产进程未配置 KMS 时必须拒绝启动。
- 自动交易默认关闭；本计划仅开放受风控审批的人工订单入口。
- 没有授权凭据时，只运行签名、协议和 Mock HTTP 测试，不发送真实订单。
- 外部写请求超时后订单进入 `unknown`，不得自动重放。

### Task 1: 交易路由和空帐号工作台

**Files:**

- Modify: `apps/web/src/app/AppShell.tsx`
- Modify: `apps/web/src/app/AppShell.test.tsx`
- Create: `apps/web/src/pages/trading/TradingWorkspace.tsx`
- Create: `apps/web/src/pages/trading/CnTradingPage.tsx`
- Create: `apps/web/src/pages/trading/HkUsTradingPage.tsx`
- Create: `apps/web/src/pages/trading/BinanceTradingPage.tsx`
- Create: `apps/web/src/features/trading/types.ts`
- Modify: `apps/web/src/styles/tokens.css`

#### Task 1, Step 1: 写失败测试

在 `AppShell.test.tsx` 验证：

- `/trading` 重定向到 `/trading/cn`。
- 沪深、港美、币安三个二级导航始终可见。
- 三个页面都有“添加帐号”按钮。
- 币安页显示现货、全仓、逐仓、U 本位产品标签。
- 初始状态不渲染虚构资产和订单。

#### Task 1, Step 2: 运行测试并确认失败

Run: `pnpm --filter web test -- AppShell.test.tsx`

Expected: FAIL，缺少交易子路由和产品标签。

#### Task 1, Step 3: 实现最小工作台

使用共享 `TradingWorkspace` 渲染市场标签、帐号摘要、帐号表格和空状态。证券页仅
传入允许的通道，币安页额外渲染产品标签与生产风险闸门。

#### Task 1, Step 4: 验证

Run: `pnpm --filter web test -- AppShell.test.tsx`

Expected: PASS。

#### Task 1, Step 5: 提交

```bash
git add apps/web
git commit -m "feat: add trading market workspaces"
```

### Task 2: 帐号绑定交互和敏感字段清理

**Files:**

- Create: `apps/web/src/features/trading/AccountBindingDialog.tsx`
- Create: `apps/web/src/features/trading/AccountBindingDialog.test.tsx`
- Create: `apps/web/src/features/trading/api.ts`
- Modify: `apps/web/src/pages/trading/TradingWorkspace.tsx`
- Modify: `apps/web/src/styles/tokens.css`

#### Task 2, Step 1: 写失败测试

验证证券通道白名单、币安凭据类型、四个 Scope、固定出口 IP 确认，以及保存或
取消后 API Key 和私钥不再出现在 DOM 中。

#### Task 2, Step 2: 运行测试并确认失败

Run: `pnpm --filter web test -- AccountBindingDialog.test.tsx`

Expected: FAIL，组件不存在。

#### Task 2, Step 3: 实现

表单使用受控状态。币安生产绑定默认 `ed25519`，凭据字段关闭自动填充；未确认
IP 白名单或未选择 Scope 时禁止保存。页面只展示帐号指纹、连接状态和权限状态。

#### Task 2, Step 4: 验证

Run: `pnpm --filter web test -- AccountBindingDialog.test.tsx`

Expected: PASS，测试输出和 DOM 均不包含明文凭据。

#### Task 2, Step 5: 提交

```bash
git add apps/web
git commit -m "feat: add secure trading account binding"
```

### Task 3: Trading 服务帐号域和迁移

**Files:**

- Create: `services/trading/pyproject.toml`
- Create: `services/trading/src/trading/config.py`
- Create: `services/trading/src/trading/db.py`
- Create: `services/trading/src/trading/models.py`
- Create: `services/trading/src/trading/security.py`
- Create: `services/trading/src/trading/secrets.py`
- Create: `services/trading/src/trading/accounts.py`
- Create: `services/trading/migrations/versions/0001_trading_core.py`
- Create: `services/trading/tests/conftest.py`
- Create: `services/trading/tests/test_accounts.py`

#### Task 3, Step 1: 写失败测试

覆盖租户隔离、通道白名单、币安仅生产环境、Scope 白名单、逐仓交易对要求、
凭据不回显、提现权限拒绝、非管理员拒绝和近期 MFA 要求。

#### Task 3, Step 2: 运行测试并确认失败

Run: `uv run pytest services/trading/tests/test_accounts.py -v`

Expected: FAIL，`trading` 包不存在。

#### Task 3, Step 3: 实现帐号域

建立 `trading_accounts`、`trading_account_scopes`、`orders` 和
`local_encrypted_secrets`。`TradingAccountService` 接收可替换的权限探测器和
SecretBackend，事务失败时清除凭据。响应模型只含 KMS 状态、Key 指纹和权限结果。

#### Task 3, Step 4: 验证

Run: `uv run pytest services/trading/tests/test_accounts.py -v`

Expected: PASS。

#### Task 3, Step 5: 提交

```bash
git add services/trading uv.lock
git commit -m "feat: add trading account domain"
```

### Task 4: Binance 请求签名和只读权限探测

**Files:**

- Create: `services/trading/src/trading/binance/signing.py`
- Create: `services/trading/src/trading/binance/client.py`
- Create: `services/trading/src/trading/binance/errors.py`
- Create: `services/trading/tests/test_binance_signing.py`
- Create: `services/trading/tests/test_binance_client.py`

#### Task 4, Step 1: 写失败测试

使用固定时间和 HTTP Mock 覆盖：

- HMAC、RSA、Ed25519 签名可验证。
- `timestamp` 使用服务器时间偏移，`recvWindow` 不超过 5000ms。
- API Key 只进入请求头，Secret 不进入 URL、异常和日志。
- 权限探测分别访问 Spot、Margin、USD-M 帐号端点。
- HTTP 429、418、签名失败和时钟偏差映射为稳定错误码。

#### Task 4, Step 2: 运行测试并确认失败

Run:

```bash
uv run pytest \
  services/trading/tests/test_binance_signing.py \
  services/trading/tests/test_binance_client.py -v
```

Expected: FAIL，连接器模块不存在。

#### Task 4, Step 3: 实现

使用 `cryptography` 解析 Ed25519 和 RSA 私钥，HMAC 使用 SHA-256。客户端仅允许
官方 HTTPS Host，签名参数按编码后的查询串计算；时间偏移先通过公开时间端点校准。

#### Task 4, Step 4: 验证

Run:

```bash
uv run pytest \
  services/trading/tests/test_binance_signing.py \
  services/trading/tests/test_binance_client.py -v
```

Expected: PASS，Mock 历史请求中无 Secret。

#### Task 4, Step 5: 提交

```bash
git add services/trading
git commit -m "feat: add binance signed connector"
```

### Task 5: 现货、杠杆和 U 本位订单路由

**Files:**

- Create: `services/trading/src/trading/orders.py`
- Create: `services/trading/src/trading/risk.py`
- Modify: `services/trading/src/trading/binance/client.py`
- Create: `services/trading/tests/test_orders.py`
- Modify: `packages/contracts/proto/trading/v1/trading.proto`

#### Task 5, Step 1: 写失败测试

覆盖四个 Scope 的端点和参数映射、逐仓 `isIsolated=TRUE`、杠杆 side effect、
U 本位 `positionSide/reduceOnly`、重复幂等键、急停、未启用交易、风控拒绝，以及
写请求超时进入 `unknown` 后只允许查询。

#### Task 5, Step 2: 运行测试并确认失败

Run: `uv run pytest services/trading/tests/test_orders.py -v`

Expected: FAIL，订单服务不存在。

#### Task 5, Step 3: 实现

订单先以 `pending_submit` 和请求指纹落库。调用 Connector 前执行帐号、Scope、
MFA、风险审批和急停检查。成功后保存交易所订单号；业务拒绝保存 `rejected`；
网络超时保存 `unknown`，且不执行自动重试。

#### Task 5, Step 4: 验证

Run: `uv run pytest services/trading/tests/test_orders.py -v`

Expected: PASS。

#### Task 5, Step 5: 提交

```bash
git add services/trading packages/contracts
git commit -m "feat: route protected binance orders"
```

### Task 6: FastAPI、健康检查和本地运行

**Files:**

- Create: `services/trading/src/trading/api/accounts.py`
- Create: `services/trading/src/trading/api/orders.py`
- Create: `services/trading/src/trading/api/health.py`
- Create: `services/trading/src/trading/main.py`
- Create: `services/trading/tests/test_api.py`
- Modify: `infra/compose/docker-compose.yml`
- Modify: `scripts/wait_for_services.sh`

#### Task 6, Step 1: 写失败测试

验证 RFC 7807 错误、Bearer 身份、`Idempotency-Key`、近期 MFA、列表租户隔离、
帐号绑定、连接测试、启用交易、下单、查询、撤单和急停。

#### Task 6, Step 2: 运行测试并确认失败

Run: `uv run pytest services/trading/tests/test_api.py -v`

Expected: FAIL，API 路由不存在。

#### Task 6, Step 3: 实现

API 只接受经 JWT 验证的租户上下文。生产写接口缺少风控服务、KMS、固定出口声明
或近期 MFA 时返回明确错误，不降级执行。

#### Task 6, Step 4: 验证

Run: `uv run pytest services/trading/tests/test_api.py -v`

Expected: PASS。

#### Task 6, Step 5: 提交

```bash
git add services/trading infra scripts
git commit -m "feat: expose protected trading api"
```

### Task 7: 全量验证和文档同步

**Files:**

- Modify: `docs/requirements/requirements-traceability-matrix.md`
- Modify: `docs/test/test-cases.md`
- Create: `docs/integrations/binance-production-readiness.md`

#### Task 7, Step 1: 运行静态检查和单元测试

Run:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy services/trading/src
uv run pytest
pnpm --filter web lint
pnpm --filter web test
pnpm --filter web build
```

Expected: 全部 PASS。

#### Task 7, Step 2: Playwright 验证

按 `webapp-testing` 流程，在桌面和移动视口验证三个交易页、绑定弹窗、键盘焦点、
敏感字段清除、水平导航和无文本重叠。

#### Task 7, Step 3: 安全检查

Run:

```bash
uv run bandit -r services/trading/src
git diff --check
rg -n "api[_-]?key|private[_-]?key|secret" services/trading apps/web
```

Expected: 无硬编码凭据、无明文回显、无高危告警。

#### Task 7, Step 4: 更新状态

追踪矩阵仅将已自动验证的条目标记为 `Implemented`；真实资金灰度保持
`Blocked by credentials/compliance`，并列出 KMS、固定出口 IP、币安权限和人工
审批证据。

#### Task 7, Step 5: 最终提交

```bash
git add .
git commit -m "feat: implement binance production trading foundation"
```

# Binance 单账号分阶段实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement
> this plan task-by-task.

**Goal:** 先交付单账号只读查询，再增加受 MFA、幂等和 Runtime 状态保护的人工
交易。

**Architecture:** React Web 调用 Identity 与 Trading。Trading 使用 MySQL、
本地 AES-256-GCM 凭据库和进程内 NautilusTrader Spot/USD-M Runtime。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy、MySQL、NautilusTrader
1.231.0、React 19、TypeScript、Vitest、pytest、Docker Compose。

---

## 当前状态

| 阶段 | 状态 | 说明 |
| --- | --- | --- |
| 单账号 API | 完成 | 查询、替换、删除 |
| 注册与数据库约束 | 完成 | 生产单所有者、全局唯一 Binance 账号 |
| 安全替换 | 完成 | 候选验证、事务与补偿 |
| Runtime 生命周期 | 完成 | 启动恢复、关闭停止、异常时拒绝就绪 |
| MFA 基础门禁 | 完成 | 敏感账号写入要求 5 分钟内 MFA |
| 权限探测 | 完成 | 仅允许读取 API 权限 |
| 账户概览 | 完成 | Spot/USD-M、5 秒快照、局部降级 |
| Web 页面 | 完成 | 首页行情/资讯、策略表格、交易行情/资产/订单 |
| 阶段一部署 | 完成 | ECS 服务和迁移健康 |
| 真实只读验收 | 阻塞 | Binance 签名接口出口不可达 |
| 阶段二 | 未开始 | 必须等待阶段一真实验收 |

## 已完成契约

```text
GET    /api/v1/trading/binance/account
PUT    /api/v1/trading/binance/account
DELETE /api/v1/trading/binance/account
GET    /api/v1/trading/binance/overview
GET    /api/v1/trading/health
GET    /health/binance
```

阶段一回归：

```bash
uv run pytest services/trading/tests -q
pnpm --filter web test
pnpm --filter web build
```

真实只读测试默认跳过，只有显式配置以下变量才运行：

```text
RUN_BINANCE_PRODUCTION_READ_ONLY_TESTS=true
BINANCE_UAT_BASE_URL=<trusted HTTPS URL>
BINANCE_UAT_BEARER_TOKEN=<short-lived token>
BINANCE_PRODUCTION_API_KEY=<secret>
BINANCE_PRODUCTION_API_SECRET=<secret>
```

## Task 8: MFA 写入门禁

**Files:**

- Modify: `services/trading/src/trading/security.py`
- Modify: `services/trading/src/trading/api/binance_account.py`
- Modify: `services/identity-tenant/src/identity_tenant/auth.py`

P0 已完成：

- 查询不要求 MFA，账号绑定、替换和删除要求 5 分钟内完成 MFA。
- 缺失或过期统一返回 `auth.mfa_required`。
- 实盘写入统一先检查 `LIVE_TRADING_ENABLED`，关闭时返回
  `trading.live_disabled`，再检查 MFA。
- 阶段二在同一守卫后继续增加 Runtime、账号权限和幂等门禁。

```bash
uv run pytest \
  services/trading/tests/test_security.py \
  services/identity-tenant/tests/test_auth.py -v
```

## Task 9: Nautilus 下单与撤单

**Files:**

- Create: `services/trading/src/trading/binance_orders.py`
- Create: `services/trading/src/trading/api/binance_orders.py`
- Create: `services/trading/tests/test_binance_orders.py`
- Reference: `services/trading/migrations/versions/0001_trading_core.py` 的既有
  `trading_orders` / `trading_operations` 契约
- Create: `services/trading/migrations/versions/0006_binance_order_contract.py`
- Modify: `services/trading/src/trading/binance_runtime/manager.py`
- Modify: `services/trading/src/trading/models.py`
- Modify: `services/trading/src/trading/main.py`

接口：

```text
GET  /api/v1/trading/binance/orders
POST /api/v1/trading/binance/orders
POST /api/v1/trading/binance/orders/{order_id}/cancel
```

`trading_orders` 和 `trading_operations` 已由 `0001` 创建，`0006` 只做字段或
约束演进，不得重复建表。测试必须覆盖 Spot/USD-M 市价与限价映射、参数校验、
幂等冲突、权限与 Runtime 门禁、明确拒绝和 `pending_reconciliation`。

## Task 10: USD-M 设置

**Files:**

- Create: `services/trading/src/trading/binance_futures.py`
- Create: `services/trading/src/trading/api/binance_futures.py`
- Create: `services/trading/tests/test_binance_futures.py`
- Modify: `services/trading/src/trading/binance_runtime/manager.py`
- Modify: `services/trading/src/trading/main.py`

接口：

```text
PUT /api/v1/trading/binance/futures/{symbol}/leverage
PUT /api/v1/trading/binance/futures/{symbol}/margin-mode
```

只允许交易所支持的杠杆范围和 `cross|isolated`。每次写入要求独立幂等键；失败或
超时不得伪造成功。

## Task 11: 人工交易页面

**Files:**

- Create: `apps/web/src/features/trading/BinanceOrderTicket.tsx`
- Create: `apps/web/src/features/trading/BinanceOrdersTable.tsx`
- Create: `apps/web/src/features/trading/BinanceFuturesSettings.tsx`
- Modify: `apps/web/src/pages/TradingPage.tsx`
- Modify: `apps/web/src/features/trading/api.ts`
- Modify: `apps/web/src/features/trading/types.ts`

交易页当前由 `TradingPage.tsx` 组合左侧 BTC/USDT 行情、右侧
`BinanceAssetsPanel.tsx` 资产概览，以及「订单」六列表格。阶段一订单表在表格内
展示空态；阶段二在该区块接入真实订单数据、下单票据与 USD-M 设置，只提供
市价、限价、单笔撤单、杠杆和保证金模式。交易区域受功能开关和 MFA 会话保护；
`pending_reconciliation` 不提供重试按钮。新增表单和操作应沿用现有单行工具栏、
表格与响应式规范。

## Task 12: Testnet 与生产门禁

**Files:**

- Create: `tests/integration/binance/test_spot_orders.py`
- Create: `tests/integration/binance/test_usdm_orders.py`
- Create: `tests/integration/binance/test_reconciliation.py`
- Modify: `docs/integrations/binance-production-readiness.md`
- Modify: `docs/operations/binance-nautilustrader-runbook.md`

没有以下配置时全部跳过，不得回退生产：

```text
BINANCE_TESTNET_ENABLED=true
BINANCE_TESTNET_API_KEY=<secret>
BINANCE_TESTNET_SECRET=<secret>
```

必须验证 Spot/USD-M 下单、撤单、杠杆、保证金模式、断线、重启和不确定结果
对账，确认不存在重复订单。

## 最终验证

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy services/identity-tenant/src services/trading/src
uv run pytest
uv run bandit -r services/identity-tenant/src services/trading/src
pnpm lint
pnpm test
pnpm build
git diff --check
```

生产启用条件：

1. 阶段一真实只读验收通过。
2. Testnet 生命周期与故障演练通过。
3. `pending_reconciliation` 可收敛。
4. 人工批准 `LIVE_TRADING_ENABLED=true`。

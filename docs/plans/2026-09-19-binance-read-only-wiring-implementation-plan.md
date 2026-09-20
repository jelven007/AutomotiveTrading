# Binance Read-only Account Wiring Implementation Plan

**Superseded（2026-09-20）：** 本计划已由
[`QT-PLAN-BIN-NT-001`](2026-09-20-binance-nautilustrader-integration-implementation-plan.md)
取代，不得继续按本文实施。

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task.

**Goal:** 接通币安生产只读帐号绑定所需的权限语义、KMS/Risk/Trading 单机 UAT
编排、数据库和 Web 代理。

**Architecture:** 帐号绑定只校验读取能力和禁止提现，交易启用阶段才校验 Scope
交易权限。新增显式 `binance-readonly` Compose Profile；UAT Docker 网络可通过
受限开关使用内部 HTTP，生产继续强制 HTTPS。

**Tech Stack:** FastAPI、SQLAlchemy、Docker Compose、Nginx、pytest、Vitest。

---

## Task 1: 只读帐号绑定

### Task 1 Files

- Modify: `services/trading/src/trading/accounts.py`
- Modify: `services/trading/tests/test_accounts.py`
- Modify: `services/trading/tests/test_api.py`

### Task 1 Step 1: Write the failing test

增加测试：`can_read=true`、所有交易权限为 `false`、提现权限为 `false` 时绑定成功，
帐号状态为 `read_only` 且所有 Scope 保持禁用；启用交易仍失败。

### Task 1 Step 2: Run test to verify it fails

Run:

```bash
uv run pytest services/trading/tests/test_accounts.py -v
```

Expected: FAIL，当前绑定会因缺少 Scope 交易权限被拒绝。

### Task 1 Step 3: Write minimal implementation

拆分绑定权限校验和交易权限校验。绑定只检查读取和提现权限，`enable_trading`
继续检查每个 Scope 的实际交易权限。

### Task 1 Step 4: Run test to verify it passes

Run:

```bash
uv run pytest \
  services/trading/tests/test_accounts.py \
  services/trading/tests/test_api.py -v
```

Expected: PASS。

## Task 2: 受限内部 HTTP

### Task 2 Files

- Modify: `services/trading/src/trading/config.py`
- Modify: `services/trading/src/trading/secrets.py`
- Modify: `services/trading/src/trading/risk.py`
- Modify: `services/trading/src/trading/api/dependencies.py`
- Modify: `services/trading/tests/test_config.py`
- Modify: `services/trading/tests/test_internal_service_clients.py`

### Task 2 Step 1: Write the failing test

覆盖默认拒绝 HTTP、显式开关允许 Docker 服务名、生产环境禁止开关。

### Task 2 Step 2: Implement and verify

Run:

```bash
uv run pytest \
  services/trading/tests/test_config.py \
  services/trading/tests/test_internal_service_clients.py -v
```

Expected: PASS。

## Task 3: UAT Compose Profile

### Task 3 Files

- Modify: `infra/compose/mysql/init.sql`
- Create: `infra/compose/mysql/ensure-readonly-databases.sh`
- Modify: `infra/compose/docker-compose.deploy.yml`
- Modify: `infra/compose/.env.deploy.example`
- Modify: `scripts/deploy.sh`
- Modify: `scripts/tests/test_deployment_files.py`

### Task 3 Step 1: Write the failing test

验证 `qt_kms` 数据库、三个服务及迁移任务、Profile、强随机服务令牌和只读启动前
配置检查。

### Task 3 Step 2: Implement

新增 `readonly-up` 命令。默认 `up` 不启动 Profile；只读 Profile 固定
`LIVE_TRADING_ENABLED=false`，KMS/Risk 不暴露公网。启动前必须确认 KMS
配置、固定出口 IP 白名单和公网 HTTPS 终止均已完成。

### Task 3 Step 3: Verify

Run:

```bash
uv run pytest scripts/tests/test_deployment_files.py -v
docker compose \
  --env-file infra/compose/.env.deploy.example \
  -f infra/compose/docker-compose.yml \
  -f infra/compose/docker-compose.deploy.yml \
  --profile binance-readonly config --quiet
```

Expected: PASS。

## Task 4: Web 代理与文档

### Task 4 Files

- Modify: `apps/web/nginx.conf`
- Modify: `services/trading/.env.example`
- Modify: `docs/operations/deployment-and-operations.md`
- Modify: `docs/integrations/binance-production-readiness.md`

### Task 4 Step 1: Write the failing deployment test

验证 Web 存在 `/api/v1/trading` 反向代理，且 Trading 未启动时不会导致 Nginx
启动失败。

### Task 4 Step 2: Implement and verify

使用 Docker DNS 动态解析 Trading upstream，补齐 UAT 配置说明和真实只读帐号
操作步骤。

## Task 5: Full verification and commit

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

Commit:

```bash
git add .
git commit -m "feat: wire binance read-only account mode"
```

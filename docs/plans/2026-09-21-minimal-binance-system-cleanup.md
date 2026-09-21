# Minimal Binance System Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement
> this plan task-by-task.

**Goal:** 将仓库收敛为仅包含 Web、Identity、Trading、MySQL 和 Binance
集成的最小可运行系统。

**Architecture:** 保留 React Web、FastAPI Identity、FastAPI Trading 与单个
MySQL。Trading 仅暴露 Binance 单账号和只读概览；阶段二交易能力继续按当前
Binance 分阶段计划新增，不保留旧通用多账号、Risk/KMS 或事件基础设施代码。

**Tech Stack:** React 19、TypeScript、FastAPI、SQLAlchemy、MySQL、
NautilusTrader 1.231.0、Docker Compose。

> 后续演进：本计划完成后，前端在此最小基线上重新引入了首页、策略、交易三个
> 一级页面。当前前端结构以
> [Web 前端三页全流程设计](../frontend/2026-09-21-web-three-page-design.md)
> 为准；下文 Task 2 记录的是当时的精简决策。

---

## Tasks

### Task 1: 删除无关模块

**Delete:**

- `services/audit`
- `services/instrument-market`
- `services/kms-adapter`
- `services/model-config`
- `services/mootdx-collector`
- `services/risk`
- `services/_template`
- `packages`
- `infra/helm`
- `infra/observability`
- `infra/terraform`
- `tests/contract`
- 与 A 股、模型、旧平台架构有关的文档和报告

**Verification:**

```bash
rg -n "instrument-market|mootdx|model-config|kms-adapter|risk-service|kafka" \
  --glob '!uv.lock' --glob '!pnpm-lock.yaml'
```

Expected: 不存在活动代码或部署引用。

### Task 2: 精简 Web

**Keep:**

- `src/features/auth`
- `src/features/trading/AccountBindingDialog.tsx`
- `src/features/trading/BinanceAccountOverview.tsx`
- `src/pages/trading/BinanceTradingPage.tsx`
- `src/pages/UserProfilePage.tsx`

**Delete:**

- 行情、模型、资讯、策略和其他市场页面
- 通用 `TradingWorkspace`
- 通用多账号 API 与类型

**Modify:**

- `/` 和 `/trading` 均跳转 `/trading/binance`
- 顶部导航只保留“币安”
- 注册表单只要求邮箱和密码
- Nginx 只代理 Identity 与 Trading
- CSS 只保留现存页面使用的样式

**Verification:**

```bash
pnpm --filter web lint
pnpm --filter web test
pnpm --filter web build
```

### Task 3: 精简 Trading

**Delete:**

- 通用账号、通用订单、账户操作、Risk、Outbox 及对应 API 和测试
- KMS/Fernet 生产兼容代码

**Keep:**

- Binance 单账号替换与删除
- 最小权限探测
- Nautilus Spot/USD-M Runtime
- 聚合账户概览
- AES-256-GCM 本地凭据存储
- JWT、Trace、健康检查和 Alembic 历史

**Modify:**

- 将 Binance 权限 DTO 移入 Binance 模块
- 模型只映射当前 Binance 账号和本地密文
- `main.py` 只注册健康、Binance 账号和概览路由
- 生产写入开关继续默认关闭，供阶段二使用

**Verification:**

```bash
uv run ruff check services/trading
uv run mypy services/trading/src
uv run pytest services/trading/tests -q
```

### Task 4: 精简部署与工作区

**Modify:**

- `infra/compose/docker-compose.yml` 只保留 MySQL、Identity、Trading、Web
- `scripts/deploy.sh` 只保留 `init/up/status/logs/restart/down`
- `Makefile`、Python workspace、pnpm workspace 和依赖锁文件
- CI 继续执行 lint、test、build

**Delete:**

- `infra/compose/docker-compose.deploy.yml`
- Kafka、ClickHouse、MinIO、Mailpit 初始化文件
- 服务生成器、协议生成器和旧等待脚本

**Verification:**

```bash
docker compose --env-file infra/compose/.env.deploy.example \
  -f infra/compose/docker-compose.yml config --quiet
bash -n scripts/deploy.sh
bash scripts/check_workspace.sh
```

### Task 5: 收敛文档并全量验收

**Keep:**

- 根 `README.md`
- `docs/README.md`
- 当前 Binance 设计、实施计划与本清理计划
- Binance 生产准入和运维手册

**Verification:**

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy services/identity-tenant/src services/trading/src
uv run pytest
pnpm lint
pnpm test
pnpm build
git diff --check
```

### Task 6: 更新 ECS

1. 备份 MySQL 和部署环境文件。
2. 同步精简仓库。
3. 重建 Identity、Trading 与 Web。
4. 使用 `docker compose --remove-orphans` 删除无关容器，不删除数据卷。
5. 验证健康检查、认证门禁、Binance 缺失账号响应和写入关闭状态。

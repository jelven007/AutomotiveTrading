# MOOTDX 单源与行情页精简实施计划

<!-- markdownlint-disable MD013 -->

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 从 A 股行情方案、运行配置和页面中彻底移除 Tushare，仅保留 MOOTDX 沪深采集，并精简行情工作台。

**Architecture:** MOOTDX Sidecar 负责沪深证券候选集合与行情采集，核心服务保存和查询原始及标准数据。系统不再进行外部主数据补齐或双源对账，覆盖率只描述 MOOTDX 候选集合内的采集结果。

**Tech Stack:** mootdx 0.11.7、FastAPI、ClickHouse、SQLite WAL、React 19、TanStack Virtual、Vitest、Playwright。

---

## Task 1：移除 Tushare 运行逻辑

**Files:**

- Modify: `services/mootdx-collector/src/mootdx_collector/config.py`
- Modify: `services/mootdx-collector/src/mootdx_collector/universe.py`
- Modify: `services/mootdx-collector/src/mootdx_collector/collector.py`
- Modify: `services/instrument-market/src/instrument_market/config.py`
- Modify: `services/instrument-market/src/instrument_market/providers/models.py`
- Modify: `services/instrument-market/src/instrument_market/api/catalog.py`
- Modify: `services/instrument-market/src/instrument_market/services/market_view.py`
- Modify: related tests and contracts

1. 删除 Token 配置、外部 HTTP 调用和权威名单合并逻辑。
2. 将 universe 来源固定为 `mootdx`，移除 verification/authority_error。
3. 数据目录只声明 MOOTDX，证券完整性标记为 `candidate_universe`。
4. 运行 Sidecar、核心和契约测试。

## Task 2：清理部署配置

**Files:**

- Modify: `infra/compose/.env.deploy.example`
- Modify: `infra/compose/docker-compose.deploy.yml`
- Modify: `services/instrument-market/.env.example`
- Modify: `services/mootdx-collector/.env.example`
- Modify: `scripts/deploy.sh`

1. 删除所有 `TUSHARE_TOKEN` 示例、自动补全和容器环境变量。
2. 验证 Compose 渲染与部署脚本测试。

## Task 3：全面更新文档

**Files:**

- Modify: A 股专项需求、设计、实施计划、测试计划与验收记录
- Modify: 总需求、总规格、技术方案、测试规格和文档索引
- Modify: two service README files

1. 将双源架构统一改为 MOOTDX 单源。
2. 删除 Tushare 校验、回填、故障和 Token 安全条目。
3. 明确“全市场”是 MOOTDX 前缀筛选得到的沪深候选集合。
4. 保留历史运行事实，但不再把缺少外部校准列为待办。
5. 搜索全仓，确认业务文档、代码和配置中无 Tushare 残留。

## Task 4：精简 Web 行情页

**Files:**

- Modify: `apps/web/src/features/market-data/types.ts`
- Modify: `apps/web/src/features/market-data/MarketOverviewPage.tsx`
- Modify: `apps/web/src/features/market-data/MarketTable.tsx`
- Modify: `apps/web/src/styles/tokens.css`
- Modify: related Web tests

1. 概览从五项收敛为覆盖、上交所、深交所三项。
2. 工具栏只保留搜索、交易所分段和刷新。
3. 表格只保留证券、最新价、涨跌幅、成交额、源时间和质量。
4. 移除 Tushare 核验文案、排序/质量下拉和 ClickHouse 技术标签。
5. 使用 Playwright 验证 1440 px 与 390 px 页面。

## Task 5：运行与交付

1. 执行 Ruff、Mypy、Pytest、Vitest、ESLint、构建和 Markdown 检查。
2. 重建 `instrument-market`，重启 MOOTDX LaunchAgent 与 Web。
3. 验证 `/api/v1/market/quotes/latest` 返回 5,226 条候选证券。
4. 合并到 `main`，保持 `http://127.0.0.1:7173/data` 可访问。

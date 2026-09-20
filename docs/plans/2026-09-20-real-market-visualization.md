# 沪深真实行情可视化实施计划

<!-- markdownlint-disable MD013 -->

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 启动可访问的 Web 服务，在 `/data` 页面展示 ClickHouse 中真实采集的沪深 A 股最新行情、覆盖状态和质量信息。

**Architecture:** `instrument-market` 提供只读最新快照接口，查询 ClickHouse 的沪深标准行情并关联最近证券全集和覆盖报告。React 页面通过同源 `/api/v1/market` 接口每 5 秒刷新，使用虚拟滚动展示约 5,200 行，不让浏览器连接数据库或接触内部令牌。

**Tech Stack:** FastAPI、ClickHouse HTTP、React 19、TypeScript、TanStack Virtual、Vitest、Playwright、Vite/Nginx。

---

## 本地访问调整

2026-09-20 更新：Web 固定端口改为 `7173`，本地应用不再展示登录、注册或退出入口。
应用直接使用固定 `local-workspace` 租户上下文；身份服务代码保留，
但不作为本地行情页面门禁。

## 设计基线

- **颜色：** 页面底色 `#f3f5f7`、内容底色 `#ffffff`、边界 `#dfe4e8`、
  操作蓝 `#1468d4`、A 股上涨红 `#c63c3c`、下跌绿 `#087f5b`。
- **字体：** 文字沿用 Inter/苹方；价格、成交量、代码和时间使用
  SFMono/Consolas 等宽字体。
- **布局：** 顶部应用栏下依次为标题与刷新状态、横向指标带、筛选工具栏、
  单个全宽虚拟行情表。左对齐，不使用嵌套卡片或装饰阴影。
- **范围：** 只展示 SSE/SZSE；名称来自最近证券全集报告，覆盖分母来自最新
  coverage 报告的沪深分项。
- **状态：** 加载、请求失败、空数据、陈旧、无效和未核验均有文字说明，
  不仅依赖颜色。

```text
┌ 沪深行情                         数据时间  刷新 ┐
├ 覆盖 5226/5226 │ 上交所 2320 │ 深交所 2906 │ 质量 ┤
├ 搜索代码/名称  [沪深|上交所|深交所] [全部质量] ┤
├ 代码/名称 │ 最新价 │ 涨跌幅 │ 开/高/低 │ 成交 │ 时间 │
│                  虚拟滚动行情行                    │
└──────────────────────────────────────────────────┘
```

## Task 1：实现最新行情查询服务

**Files:**

- Modify: `services/instrument-market/src/instrument_market/storage/clickhouse.py`
- Create: `services/instrument-market/src/instrument_market/services/market_view.py`
- Create: `services/instrument-market/src/instrument_market/api/quotes.py`
- Modify: `services/instrument-market/src/instrument_market/main.py`
- Test: `services/instrument-market/tests/test_market_view.py`
- Modify: `services/instrument-market/tests/test_api.py`

1. 为 ClickHouse 客户端增加带参数的 `JSONEachRow` 查询方法。
2. 先编写服务测试，覆盖沪深过滤、名称清理、涨跌计算和旧 BSE 报告排除。
3. 实现最新行情、证券名称及覆盖报告聚合。
4. 新增 `GET /api/v1/market/quotes/latest?limit=6000`，要求 `X-Tenant-ID`。
5. 运行：
   `uv run pytest services/instrument-market/tests/test_market_view.py services/instrument-market/tests/test_api.py -v`。

## Task 2：实现虚拟行情页面

**Files:**

- Modify: `apps/web/package.json`
- Modify: `pnpm-lock.yaml`
- Create: `apps/web/src/features/market-data/types.ts`
- Create: `apps/web/src/features/market-data/api.ts`
- Create: `apps/web/src/features/market-data/MarketTable.tsx`
- Create: `apps/web/src/features/market-data/MarketOverviewPage.tsx`
- Modify: `apps/web/src/pages/DataPage.tsx`
- Modify: `apps/web/src/styles/tokens.css`
- Modify: `apps/web/vite.config.ts`
- Test: `apps/web/src/features/market-data/MarketOverviewPage.test.tsx`

1. 加入 `@tanstack/react-virtual`，不手写虚拟列表引擎。
2. 编写交互测试，覆盖真实接口请求头、指标、搜索、交易所与质量筛选。
3. 实现 5 秒轮询、手动刷新、错误重试和虚拟行情表。
4. 增加 `/api/v1/market` 到本地 Vite 代理。
5. 运行 Web 单测、TypeScript/ESLint 和生产构建。

## Task 3：对齐沪深采集范围

**Files:**

- Modify: `services/mootdx-collector/src/mootdx_collector/provider.py`
- Modify: `services/mootdx-collector/src/mootdx_collector/universe.py`
- Modify: `services/instrument-market/src/instrument_market/api/ingestion.py`
- Modify: existing provider/universe/API tests

1. 移除 BSE 调度，保留 SSE/SZSE 显式市场编号。
2. 核心接收契约仅允许 SSE/SZSE。
3. 更新旧边界测试，新增范围外证券不会进入覆盖聚合的验证。
4. 运行 Sidecar 与核心相关测试，确认状态可返回 `collected`。

## Task 4：启动与浏览器验收

**Files:**

- Modify: `apps/web/nginx.conf` only if production proxy verification exposes a gap
- Update: `docs/testing/results/mootdx-sidecar-acceptance.md`

1. 重建并重启 `instrument-market`，确认真实接口返回 5,226 只沪深候选证券。
2. 启动 Vite Web 服务，访问 `http://127.0.0.1:7173/data`。
3. 使用 Playwright 在桌面和移动视口验证直达、筛选、滚动、刷新、无重叠和控制台错误。
4. 保存截图到 `/tmp`，不提交运行截图。
5. 更新验收记录，运行格式、测试、构建与 `git diff --check`，提交并合并主分支。

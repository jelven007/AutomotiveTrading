# MOOTDX History Data Implementation Plan

<!-- markdownlint-disable MD013 MD032 -->

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 接入沪深证券最近 800 根日 K、最近交易日分时与分页分笔，并在 Web 中提供个股历史行情视图。

**Architecture:** 在 MOOTDX Sidecar 内增加独立限速历史线程，复用 SQLite WAL 和认证 HTTP 投递；`instrument-market` 将原始行与标准行写入 ClickHouse，并提供有界查询 API。历史任务按持久化证券游标渐进推进，不阻塞现有实时快照循环。

**Tech Stack:** Python 3.12, mootdx 0.11.7, tdxpy 0.2.7, SQLite, FastAPI, Pydantic, ClickHouse, React 19, TypeScript, Lightweight Charts, Vitest.

---

## Preconditions

- Worktree: `/Users/bytedance/Documents/demo_specCoding-history`
- Branch: `feat/mootdx-history-data`
- Keep `reports/` in the main worktree untouched.
- Automated tests do not access public MOOTDX nodes.
- Real acceptance uses masked node aliases and does not commit payload dumps.

### Task 1: Lock the contracts and storage schema

**Files:**
- Modify: `services/instrument-market/src/instrument_market/storage/clickhouse.py`
- Modify: `packages/contracts/openapi/market-data.yaml`
- Test: `services/instrument-market/tests/test_clickhouse.py`
- Test: `tests/contract/test_market_data_contracts.py`

**Steps:**

1. Add failing assertions for `market_history_raw`, `market_minute`, and new bar/transaction
   metadata columns.
2. Run:
   `uv run pytest services/instrument-market/tests/test_clickhouse.py tests/contract -q`
   and confirm the new assertions fail.
3. Add idempotent ClickHouse DDL. Keep existing tables and use `ALTER ... ADD COLUMN IF NOT
   EXISTS` for deployed databases.
4. Add public history query paths and internal batch schemas to OpenAPI.
5. Re-run the focused tests and commit the schema milestone.

### Task 2: Implement core ingestion and history queries

**Files:**
- Create: `services/instrument-market/src/instrument_market/services/history.py`
- Create: `services/instrument-market/src/instrument_market/api/history.py`
- Modify: `services/instrument-market/src/instrument_market/api/ingestion.py`
- Modify: `services/instrument-market/src/instrument_market/main.py`
- Test: `services/instrument-market/tests/test_history_ingestion.py`
- Test: `services/instrument-market/tests/test_history_view.py`
- Modify: `services/instrument-market/tests/test_api.py`

**Steps:**

1. Write failing tests for raw-first persistence, Asia/Shanghai to UTC conversion, `volunit`
   conversion, invalid transaction rejection, and receipt replay.
2. Implement one `HistoryIngestionService` with dataset-specific normalizers. Generate stable
   raw event IDs from `batch_id/row_index`.
3. Add authenticated `/internal/v1/market/{bars,minutes,transactions}` routes with shared batch
   validation and bounded row counts.
4. Write failing query tests for exchange/symbol validation, date/limit filters, newest-version
   selection, empty `pending` responses, and transaction `partial` coverage.
5. Implement public `/api/v1/market/{bars,minutes,transactions}/{exchange}/{symbol}` routes.
6. Run:
   `uv run pytest services/instrument-market/tests/test_history_ingestion.py services/instrument-market/tests/test_history_view.py services/instrument-market/tests/test_api.py -q`.
7. Run `uv run mypy services/instrument-market/src` and
   `uv run ruff check services/instrument-market`.
8. Commit the core milestone.

### Task 3: Implement Sidecar history collection

**Files:**
- Create: `services/mootdx-collector/src/mootdx_collector/history.py`
- Modify: `services/mootdx-collector/src/mootdx_collector/provider.py`
- Modify: `services/mootdx-collector/src/mootdx_collector/config.py`
- Modify: `services/mootdx-collector/src/mootdx_collector/__main__.py`
- Modify: `services/mootdx-collector/src/mootdx_collector/transport.py`
- Test: `services/mootdx-collector/tests/test_history.py`
- Modify: `services/mootdx-collector/tests/test_provider.py`
- Modify: `services/mootdx-collector/tests/test_transport.py`

**Steps:**

1. Write failing Provider tests for exact market/category/date arguments, 800-row limits, and
   transaction pagination.
2. Add `daily_bars`, `minute_history`, and `transaction_history` methods. Reject unsupported
   exchanges and invalid page sizes before network access.
3. Write failing history-worker tests for the 240-point clock, short-page completion, eight-page
   truncation, capacity pause, and restart cursor.
4. Implement a single low-priority worker with its own `Provider`, configurable request interval,
   and one-symbol atomic cursor advancement.
5. Extend sender acknowledgements for `bars`, `minutes`, and `transactions`.
6. Start/stop the worker from `__main__` without changing quote scheduling.
7. Run `uv run --directory services/mootdx-collector pytest -q` and
   `uv run ruff check services/mootdx-collector`.
8. Commit the Sidecar milestone.

### Task 4: Add instrument history to the Web workspace

**Files:**
- Modify: `apps/web/package.json`
- Modify: `pnpm-lock.yaml`
- Modify: `apps/web/src/features/market-data/types.ts`
- Modify: `apps/web/src/features/market-data/api.ts`
- Modify: `apps/web/src/features/market-data/MarketTable.tsx`
- Modify: `apps/web/src/features/market-data/MarketOverviewPage.tsx`
- Create: `apps/web/src/features/market-data/InstrumentHistory.tsx`
- Modify: `apps/web/src/features/market-data/MarketOverviewPage.test.tsx`
- Modify: `apps/web/src/styles/tokens.css`

**Steps:**

1. Add `lightweight-charts` using the workspace package manager.
2. Write failing tests for selecting a row, loading three history endpoints, switching tabs,
   rendering empty state, and exposing partial transaction coverage.
3. Add typed API clients and an accessible row-selection callback.
4. Implement one stable-height detail workspace with segmented tabs, chart cleanup on unmount,
   responsive sizing, and a virtualized or bounded transaction list.
5. Keep price direction, source date, coverage and quality visible without relying on color alone.
6. Run `pnpm --filter web test`, `pnpm --filter web lint`, and `pnpm --filter web build`.
7. Commit the Web milestone.

### Task 5: Deploy locally and perform real acceptance

**Files:**
- Modify: `services/mootdx-collector/.env.example`
- Modify: `infra/compose/.env.example`
- Modify: `infra/compose/.env.deploy.example`
- Modify: `infra/compose/docker-compose.deploy.yml`
- Modify: `scripts/deploy.sh`
- Modify: `services/mootdx-collector/README.md`
- Modify: `docs/testing/results/mootdx-history-acceptance.md`

**Steps:**

1. Document and wire bounded history settings; default to enabled, one worker, 250 ms minimum
   interval, 800 bars, and eight transaction pages.
2. Run the full backend, contract, deployment, and Web test suites.
3. Rebuild/restart `instrument-market`, sync the Sidecar venv, and restart its LaunchAgent.
4. Confirm real SSE and SZSE rows reach all three canonical tables and all three public APIs.
5. Open `http://127.0.0.1:7173/data`; verify one desktop and one 390 px mobile viewport with
   Playwright screenshots and browser console checks.
6. Record counts, timestamps, completeness and known Provider anomalies in the acceptance report.
7. Merge `feat/mootdx-history-data` into `main`, restart services from `main`, and re-run health
   plus smoke queries.

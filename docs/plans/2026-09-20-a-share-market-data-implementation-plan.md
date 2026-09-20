# A Share Market Data Implementation Plan

<!-- markdownlint-disable MD013 MD032 MD036 -->

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 建设仅覆盖上交所（SSE）和深交所（SZSE）A 股的个人数据服务，持久化 MOOTDX 支持的数据并提供实时分析和运维页面。

**Architecture:** Add one FastAPI `instrument-market` service with isolated collectors, an idempotent Kafka pipeline, MySQL control-plane state, ClickHouse analytical tables, MinIO raw archives, and Redis latest projections. Extend the existing React/Vite data area with virtualized market, instrument detail, data catalog, and operations views.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, SQLAlchemy, mootdx 0.11.7, Redpanda/Kafka, ClickHouse, Redis, MinIO/S3, React 19, TypeScript, TanStack Query/Virtual, Lightweight Charts, Vitest.

---

## 2026-09-20 范围基线更新

本文中的 A-share universe 和 full-market 均限定为沪深 A 股。北交所不属于
采集、历史回填、主数据补齐、查询展示、覆盖统计和验收范围。
证券范围由 MOOTDX/TDX 列表按沪深代码前缀筛选；范围外市场不计入应采数量、
不生成缺口或降级。
已交付 Sidecar 的旧范围分支仍需按
[范围对齐状态](../../services/mootdx-collector/README.md#范围对齐状态) 完成代码同步；
本次文档更新不代表该实现调整已通过测试。

## Preconditions

- Work in an isolated Git worktree.
- Keep `LIVE_TRADING_ENABLED=false`.
- Never commit a real source IP, production payload, or local absolute data path.
- Use recorded and anonymized Provider fixtures in automated tests.
- Read `docs/requirements/a-share-market-data-requirements.md`.
- Read `docs/plans/2026-09-20-a-share-market-data-design.md`.
- Read `docs/testing/a-share-market-data-test-plan.md`.

## TRAE Skill Workflow

- Use `brainstorming` before changing the approved scope or behavior.
- Use `bits-unit-test-gen` for each backend or frontend unit-test milestone.
- Use `frontend-design` before implementing the market and instrument pages.
- Use `webapp-testing` for desktop/mobile interaction and screenshot verification.
- Use `fix` before each milestone commit and before final CI verification.
- Use `code-reviewer` for the final local-change review.
- Use `TRAE-security-review` only when explicitly performing the final security audit.

### Task 1: Add contracts and schema validation

**Files:**
- Create: `packages/contracts/openapi/market-data.yaml`
- Create: `packages/contracts/jsonschema/market-quote-v1.json`
- Create: `packages/contracts/jsonschema/market-transaction-v1.json`
- Create: `packages/contracts/jsonschema/market-bar-v1.json`
- Modify: `packages/contracts/asyncapi.yaml`
- Modify: `infra/compose/kafka/create-topics.sh`
- Test: `tests/contract/test_market_data_schemas.py`

**Step 1: Write the failing contract tests**

Add tests that load every new JSON Schema, validate one complete fixture, reject missing
source timestamps, and assert the AsyncAPI topics exist.

行情契约的交易所范围限定为 SSE/SZSE，并验证范围外证券不会进入业务采集链路。

**Step 2: Run the tests and verify failure**

Run:

```bash
uv run pytest tests/contract/test_market_data_schemas.py -v
```

Expected: FAIL because the schemas and topics do not exist.

**Step 3: Define the contracts**

The quote contract must include:

```json
{
  "instrument_id": "uuid",
  "exchange": "SSE",
  "symbol": "600519",
  "source_time": "2026-09-20T01:31:02Z",
  "collected_at": "2026-09-20T01:31:02.412Z",
  "last_price": "1468.20",
  "volume": "1023400",
  "amount": "1502340000.00",
  "bids": [{"price": "1468.10", "quantity": "2300"}],
  "asks": [{"price": "1468.30", "quantity": "1200"}],
  "provider": "mootdx",
  "quality_status": "healthy",
  "schema_version": 1
}
```

Add the topics listed in the design document with an initial three partitions.

**Step 4: Run contract tests**

Run:

```bash
uv run pytest tests/contract/test_market_data_schemas.py tests/contract/test_schemas.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add packages/contracts infra/compose/kafka tests/contract
git commit -m "feat: define a-share market data contracts"
```

### Task 2: Add ClickHouse and instrument-market infrastructure

**Files:**
- Modify: `infra/compose/docker-compose.yml`
- Modify: `infra/compose/docker-compose.deploy.yml`
- Modify: `infra/compose/.env.example`
- Modify: `infra/compose/.env.deploy.example`
- Modify: `infra/compose/mysql/init.sql`
- Create: `infra/compose/clickhouse/init.sql`
- Test: `tests/integration/test_market_data_infrastructure.py`

**Step 1: Write a failing infrastructure test**

Assert that Compose defines ClickHouse health checks, persistent volumes, MinIO,
Redis, Kafka, and the `qt_instrument_market` MySQL database.

**Step 2: Run the test and verify failure**

Run:

```bash
uv run pytest tests/integration/test_market_data_infrastructure.py -v
```

Expected: FAIL because ClickHouse and the database are absent.

**Step 3: Add infrastructure**

Add ClickHouse with a bound data volume, health check, authenticated application user,
and no public production port. Create the initial tables from the approved design.

**Step 4: Verify Compose and the integration test**

Run:

```bash
docker compose -f infra/compose/docker-compose.yml config
uv run pytest tests/integration/test_market_data_infrastructure.py -v
```

Expected: both commands PASS.

**Step 5: Commit**

```bash
git add infra/compose tests/integration/test_market_data_infrastructure.py
git commit -m "feat: add clickhouse market data infrastructure"
```

### Task 3: Scaffold the instrument-market service

**Files:**
- Create: `services/instrument-market/pyproject.toml`
- Create: `services/instrument-market/Dockerfile`
- Create: `services/instrument-market/alembic.ini`
- Create: `services/instrument-market/.env.example`
- Create: `services/instrument-market/src/instrument_market/__init__.py`
- Create: `services/instrument-market/src/instrument_market/main.py`
- Create: `services/instrument-market/src/instrument_market/config.py`
- Create: `services/instrument-market/src/instrument_market/db.py`
- Create: `services/instrument-market/src/instrument_market/errors.py`
- Create: `services/instrument-market/src/instrument_market/context.py`
- Create: `services/instrument-market/src/instrument_market/middleware.py`
- Create: `services/instrument-market/src/instrument_market/observability.py`
- Create: `services/instrument-market/src/instrument_market/api/health.py`
- Test: `services/instrument-market/tests/test_health.py`

**Step 1: Write failing health and configuration tests**

Cover liveness, dependency readiness, required storage URLs, secret masking, and the
absence of absolute TDX paths in serialized settings.

**Step 2: Run the tests and verify failure**

```bash
uv run pytest services/instrument-market/tests/test_health.py -v
```

Expected: FAIL because the package is absent.

**Step 3: Implement the service shell**

Copy the repository service conventions, rename the package to `instrument_market`,
and add typed settings for MySQL, ClickHouse, Redis, Kafka, MinIO, the isolated
mootdx collector, WAL, and Reader paths.

**Step 4: Run tests and static checks**

```bash
uv run pytest services/instrument-market/tests/test_health.py -v
uv run mypy services/instrument-market/src
uv run ruff check services/instrument-market
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/instrument-market
git commit -m "feat: scaffold instrument market service"
```

### Task 4: Implement isolated mootdx collector and Provider contracts

**Files:**
- Create: `services/mootdx-collector/pyproject.toml`
- Create: `services/mootdx-collector/Dockerfile`
- Create: `services/mootdx-collector/src/mootdx_collector/`
- Create: `services/instrument-market/src/instrument_market/clients/base.py`
- Create: `services/instrument-market/src/instrument_market/clients/mootdx_collector.py`
- Create: `services/instrument-market/src/instrument_market/providers/models.py`
- Create: `services/instrument-market/tests/fixtures/`
- Test: `services/mootdx-collector/tests/`
- Test: `services/instrument-market/tests/test_provider_contracts.py`

**Step 1: Write failing Provider contract tests**

Require every collector result to include source time, collection time, Provider name,
source identity, schema version, payload hash, raw payload, and capability status.
Verify that the Sidecar requires an internal service token.

**Step 2: Verify failure**

```bash
uv run --project services/mootdx-collector pytest -v
uv run pytest services/instrument-market/tests/test_provider_contracts.py -v
```

Expected: FAIL because collector and client implementations are absent.

**Step 3: Implement adapters**

Run mootdx 0.11.7 in an isolated project because it requires `httpx < 0.26`.
Do not add mootdx to the root uv workspace and do not downgrade platform HTTP
dependencies. Wrap blocking calls with a bounded worker pool, then send raw batches
through an internal authenticated API or Kafka. MOOTDX is the only market-data Provider.

**Step 4: Verify Provider tests**

```bash
uv run --project services/mootdx-collector pytest -v
uv run pytest services/instrument-market/tests/test_provider_contracts.py -v
```

Expected: PASS without external network access.

**Step 5: Commit**

```bash
git add services/instrument-market services/mootdx-collector
git commit -m "feat: add isolated mootdx provider"
```

### Task 5: Add raw envelope, WAL, and MinIO archive

**Files:**
- Create: `services/instrument-market/src/instrument_market/pipeline/envelope.py`
- Create: `services/instrument-market/src/instrument_market/pipeline/wal.py`
- Create: `services/instrument-market/src/instrument_market/storage/minio.py`
- Create: `services/instrument-market/src/instrument_market/storage/manifest.py`
- Create: `services/instrument-market/src/instrument_market/models.py`
- Create: `services/instrument-market/migrations/versions/0001_market_control_plane.py`
- Test: `services/instrument-market/tests/test_raw_archive.py`

**Step 1: Write failing archive tests**

Test deterministic SHA-256 hashes, atomic WAL append, object path partitioning,
idempotent manifest creation, and replay after a simulated crash.

**Step 2: Verify failure**

```bash
uv run pytest services/instrument-market/tests/test_raw_archive.py -v
```

Expected: FAIL.

**Step 3: Implement raw persistence**

Write compressed NDJSON for API batches and preserve original Reader/Affair files.
Only advance a batch checkpoint after WAL fsync and archive acknowledgement.

**Step 4: Verify tests**

```bash
uv run pytest services/instrument-market/tests/test_raw_archive.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/instrument-market
git commit -m "feat: persist immutable market data payloads"
```

### Task 6: Implement instrument and reference synchronization

**Files:**
- Create: `services/instrument-market/src/instrument_market/collectors/reference.py`
- Create: `services/instrument-market/src/instrument_market/services/instruments.py`
- Create: `services/instrument-market/src/instrument_market/api/instruments.py`
- Test: `services/instrument-market/tests/test_instruments.py`

**Step 1: Write failing synchronization tests**

覆盖 SSE/SZSE 映射、证券更名、重复代码、列表刷新失败使用缓存，
以及范围外证券过滤。

**Step 2: Verify failure**

```bash
uv run pytest services/instrument-market/tests/test_instruments.py -v
```

Expected: FAIL.

**Step 3: Implement synchronization**

MOOTDX/TDX 列表按沪深代码前缀筛选候选集合。范围外市场不调度、不补齐、
不计入缺口；接口不得把候选集合描述为交易所权威全集。

**Step 4: Verify tests**

```bash
uv run pytest services/instrument-market/tests/test_instruments.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/instrument-market
git commit -m "feat: synchronize a-share instrument master"
```

### Task 7: Implement full-market quote collection

**Files:**
- Create: `services/instrument-market/src/instrument_market/collectors/quote.py`
- Create: `services/instrument-market/src/instrument_market/pipeline/checkpoint.py`
- Create: `services/instrument-market/src/instrument_market/pipeline/deduplicate.py`
- Create: `services/instrument-market/src/instrument_market/storage/kafka.py`
- Test: `services/instrument-market/tests/test_quote_collector.py`

**Step 1: Write failing quote collector tests**

Cover deterministic sharding, bounded concurrency, empty batches, server failover,
duplicate snapshots, partial rounds, cancellation, and checkpoint recovery.

**Step 2: Verify failure**

```bash
uv run pytest services/instrument-market/tests/test_quote_collector.py -v
```

Expected: FAIL.

**Step 3: Implement the collector**

Target a two-second sweep, prioritize the watchlist and active strategy pool, record
coverage for every round, and publish one event per security keyed by exchange/symbol.

分片与覆盖状态只聚合 SSE/SZSE；两个市场均完整时，不得因范围外市场状态
将轮次标记为 `partial`。源时间、数据质量及候选范围说明仍独立判断。

**Step 4: Verify tests**

```bash
uv run pytest services/instrument-market/tests/test_quote_collector.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/instrument-market
git commit -m "feat: collect full-market mootdx quotes"
```

### Task 8: Implement ClickHouse and Redis projections

**Files:**
- Create: `services/instrument-market/src/instrument_market/storage/clickhouse.py`
- Create: `services/instrument-market/src/instrument_market/storage/redis.py`
- Create: `services/instrument-market/src/instrument_market/pipeline/normalize.py`
- Create: `services/instrument-market/src/instrument_market/consumers/quotes.py`
- Test: `services/instrument-market/tests/test_quote_projection.py`

**Step 1: Write failing projection tests**

Verify Decimal preservation, unit conversion, idempotent duplicate consumption,
ClickHouse insert batches, and Redis latest replacement only by newer data.

**Step 2: Verify failure**

```bash
uv run pytest services/instrument-market/tests/test_quote_projection.py -v
```

Expected: FAIL.

**Step 3: Implement projections**

Batch ClickHouse inserts by row count or short time window. Write Redis only after the
standard record is accepted and include freshness and quality fields.

**Step 4: Verify tests**

```bash
uv run pytest services/instrument-market/tests/test_quote_projection.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/instrument-market
git commit -m "feat: project market quotes to storage"
```

### Task 9: Implement bars, minute data, and transaction pipelines

2026-09-20 首个可运行增量按
[`2026-09-20-mootdx-history-data.md`](2026-09-20-mootdx-history-data.md)
执行。该计划先交付最近 800 根未复权日 K、最近交易日分时和有界分页分笔；
全部周期、复权与多交易日回填继续保留在本任务的后续范围。

**Files:**
- Create: `services/instrument-market/src/instrument_market/collectors/bar.py`
- Create: `services/instrument-market/src/instrument_market/collectors/transaction.py`
- Create: `services/instrument-market/src/instrument_market/consumers/history.py`
- Test: `services/instrument-market/tests/test_history_collectors.py`

**Step 1: Write failing tests**

Cover the 800-row mootdx page limit, all documented frequencies, adjustment modes,
transaction fingerprints, page overlap, missing pages, and restart checkpoints.

**Step 2: Verify failure**

```bash
uv run pytest services/instrument-market/tests/test_history_collectors.py -v
```

Expected: FAIL.

**Step 3: Implement collectors**

Use persisted page cursors, bounded retries, explicit coverage intervals, and separate
high-priority queues for watchlist/strategy symbols.

**Step 4: Verify tests**

```bash
uv run pytest services/instrument-market/tests/test_history_collectors.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/instrument-market
git commit -m "feat: persist mootdx bars and transactions"
```

### Task 10: Implement Reader, F10, corporate action, and financial pipelines

**Files:**
- Create: `services/instrument-market/src/instrument_market/collectors/reader.py`
- Create: `services/instrument-market/src/instrument_market/collectors/f10.py`
- Create: `services/instrument-market/src/instrument_market/collectors/financial.py`
- Create: `services/instrument-market/src/instrument_market/consumers/reference.py`
- Test: `services/instrument-market/tests/test_reference_collectors.py`

**Step 1: Write failing tests**

Cover file hash changes, unchanged files, F10 category changes, binary content,
Affair MD5 verification, parse failures, and corporate action versioning.

**Step 2: Verify failure**

```bash
uv run pytest services/instrument-market/tests/test_reference_collectors.py -v
```

Expected: FAIL.

**Step 3: Implement low-frequency pipelines**

Preserve original bytes before parsing. Store F10 text as compressed objects and only
put searchable metadata in MySQL.

**Step 4: Verify tests**

```bash
uv run pytest services/instrument-market/tests/test_reference_collectors.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/instrument-market
git commit -m "feat: persist mootdx reference and financial data"
```

### Task 11: Implement MOOTDX data quality

**Files:**
- Create: `services/instrument-market/src/instrument_market/pipeline/quality.py`
- Create: `services/instrument-market/src/instrument_market/api/operations.py`
- Test: `services/instrument-market/tests/test_quality.py`
- Test: `services/instrument-market/tests/test_reconciliation.py`

**Step 1: Write failing quality tests**

Cover stale data, invalid OHLC, volume rollback, crossed books, price precision,
source endpoint conflicts, snapshot/bar inconsistencies, and signal eligibility.

**Step 2: Verify failure**

```bash
uv run pytest services/instrument-market/tests/test_quality.py services/instrument-market/tests/test_reconciliation.py -v
```

Expected: FAIL.

**Step 3: Implement quality decisions**

Keep provider values immutable. Store comparisons and decisions separately, with
`healthy`, `stale`, `partial`, `conflict`, `invalid`, or `unavailable` status.

**Step 4: Verify tests**

```bash
uv run pytest services/instrument-market/tests/test_quality.py services/instrument-market/tests/test_reconciliation.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/instrument-market
git commit -m "feat: add market data quality reconciliation"
```

### Task 12: Expose REST and WebSocket APIs

**Files:**
- Create: `services/instrument-market/src/instrument_market/api/quotes.py`
- Create: `services/instrument-market/src/instrument_market/api/history.py`
- Create: `services/instrument-market/src/instrument_market/api/catalog.py`
- Create: `services/instrument-market/src/instrument_market/api/websocket.py`
- Modify: `services/instrument-market/src/instrument_market/main.py`
- Test: `services/instrument-market/tests/test_api.py`
- Test: `services/instrument-market/tests/test_websocket.py`

**Step 1: Write failing API tests**

Test pagination, sort allowlists, time ranges, unsupported datasets, freshness metadata,
quality status, WebSocket sequence gaps, and REST snapshot recovery.

**Step 2: Verify failure**

```bash
uv run pytest services/instrument-market/tests/test_api.py services/instrument-market/tests/test_websocket.py -v
```

Expected: FAIL.

**Step 3: Implement the APIs**

Use cursor pagination for high-volume history. Do not return raw F10 content in list
responses. Bound all date ranges and row counts.

行情查询、频道和补采接口仅接受沪深证券，交易所筛选只提供 SSE/SZSE。

**Step 4: Verify tests**

```bash
uv run pytest services/instrument-market/tests/test_api.py services/instrument-market/tests/test_websocket.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add services/instrument-market
git commit -m "feat: expose market data query and stream APIs"
```

### Task 13: Build the full-market frontend

**Files:**
- Create: `apps/web/src/features/market-data/types.ts`
- Create: `apps/web/src/features/market-data/api.ts`
- Create: `apps/web/src/features/market-data/useQuoteStream.ts`
- Create: `apps/web/src/features/market-data/MarketTable.tsx`
- Create: `apps/web/src/pages/data/MarketOverviewPage.tsx`
- Modify: `apps/web/src/app/AppShell.tsx`
- Modify: `apps/web/src/styles/tokens.css`
- Test: `apps/web/src/features/market-data/MarketTable.test.tsx`

**Step 1: Write failing interaction tests**

Test search, filters, virtual rows, fresh/stale labels, sequence-gap recovery, row
navigation, watchlist action, keyboard focus, and non-color status text.

**Step 2: Verify failure**

```bash
pnpm --filter web test -- MarketTable
```

Expected: FAIL.

**Step 3: Implement the page**

Add TanStack Query/Virtual. Use the existing cold-white/blue visual system, add
market-specific red-up/green-down tokens, and render only visible rows.

“全市场”页面仅展示沪深证券及其覆盖率，交易所选项为上交所和深交所。

**Step 4: Verify tests and build**

```bash
pnpm --filter web test -- MarketTable
pnpm --filter web lint
pnpm --filter web build
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/web pnpm-lock.yaml
git commit -m "feat: add real-time a-share market page"
```

### Task 14: Build instrument analysis pages

**Files:**
- Create: `apps/web/src/pages/data/InstrumentDetailPage.tsx`
- Create: `apps/web/src/features/market-data/MarketChart.tsx`
- Create: `apps/web/src/features/market-data/OrderBook.tsx`
- Create: `apps/web/src/features/market-data/TransactionTape.tsx`
- Create: `apps/web/src/features/market-data/FundamentalsView.tsx`
- Create: `apps/web/src/features/market-data/DataProvenance.tsx`
- Test: `apps/web/src/features/market-data/InstrumentDetailPage.test.tsx`

**Step 1: Write failing page tests**

Test period and adjustment controls, quote updates, stale states, unsupported Provider
capabilities, F10 loading, transaction pagination, and chart empty states.

**Step 2: Verify failure**

```bash
pnpm --filter web test -- InstrumentDetailPage
```

Expected: FAIL.

**Step 3: Implement the page**

Use Lightweight Charts for time series, a fixed-width order book, and tabs for
fundamentals, corporate actions, F10, and provenance.

**Step 4: Verify tests and build**

```bash
pnpm --filter web test -- InstrumentDetailPage
pnpm --filter web build
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/web pnpm-lock.yaml
git commit -m "feat: add a-share instrument analysis page"
```

### Task 15: Build data catalog, operations, and source settings

**Files:**
- Create: `apps/web/src/pages/data/DataCatalogPage.tsx`
- Create: `apps/web/src/pages/data/DataOperationsPage.tsx`
- Create: `apps/web/src/pages/settings/DataSourcesPage.tsx`
- Create: `apps/web/src/features/market-data/BackfillDialog.tsx`
- Modify: `apps/web/src/pages/DataPage.tsx`
- Modify: `apps/web/src/app/AppShell.tsx`
- Test: `apps/web/src/features/market-data/DataOperationsPage.test.tsx`
- Test: `apps/web/src/features/market-data/DataSourcesPage.test.tsx`

**Step 1: Write failing tests**

Test dataset coverage, collector health, gap filters, storage thresholds, bounded
backfill submission, masked credentials, and source capability display.

**Step 2: Verify failure**

```bash
pnpm --filter web test -- DataOperationsPage DataSourcesPage
```

Expected: FAIL.

**Step 3: Implement pages**

Keep operational views table-led and compact. Use icons for refresh, retry, settings,
and row actions with accessible names and tooltips.

**Step 4: Verify tests and build**

```bash
pnpm --filter web test -- DataOperationsPage DataSourcesPage
pnpm --filter web lint
pnpm --filter web build
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/web
git commit -m "feat: add market data operations pages"
```

### Task 16: Wire deployment, observability, and recovery

**Files:**
- Modify: `infra/compose/docker-compose.deploy.yml`
- Modify: `infra/observability/README.md`
- Modify: `docs/operations/deployment-and-operations.md`
- Create: `services/instrument-market/README.md`
- Create: `scripts/tests/test_market_data_deployment.py`

**Step 1: Write a failing deployment test**

Assert private service bindings, persistent volumes, health dependencies, resource
limits, required environment variables, and no secrets in rendered Compose output.

**Step 2: Verify failure**

```bash
uv run pytest scripts/tests/test_market_data_deployment.py -v
```

Expected: FAIL.

**Step 3: Wire deployment and runbooks**

Add the service, migrations, consumers, collectors, ClickHouse, backup commands,
disk-pressure behavior, Redis rebuild, Kafka replay, and Provider failover procedures.

**Step 4: Verify deployment configuration**

```bash
docker compose \
  -f infra/compose/docker-compose.yml \
  -f infra/compose/docker-compose.deploy.yml \
  config
uv run pytest scripts/tests/test_market_data_deployment.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add infra services/instrument-market/README.md scripts/tests docs/operations
git commit -m "feat: deploy a-share market data service"
```

### Task 17: Run end-to-end and capacity acceptance

**Files:**
- Create: `tests/e2e/test_a_share_market_data.py`
- Create: `tests/performance/market_data_load.py`
- Create: `docs/testing/results/a-share-market-data-capacity.md`
- Modify: `docs/requirements/requirements-traceability-matrix.md`

**Step 1: Add failing acceptance tests**

Cover empty-database initialization, one full quote sweep, raw-to-standard traceability,
Redis rebuild, backfill, WebSocket recovery, and frontend data availability.

按 `TC-CNMD-014` 验证范围外市场不进入采集与覆盖统计；真实覆盖率以当日
MOOTDX 沪深候选集合为分母，不能描述为交易所权威全集。

**Step 2: Run the acceptance suite before final wiring**

```bash
uv run pytest tests/e2e/test_a_share_market_data.py -v
```

Expected: FAIL until all runtime services are wired.

**Step 3: Execute the integration environment**

```bash
docker compose \
  -f infra/compose/docker-compose.yml \
  -f infra/compose/docker-compose.deploy.yml \
  up -d --build
uv run pytest tests/e2e/test_a_share_market_data.py -v
```

Expected: PASS.

**Step 4: Execute load and UI verification**

```bash
uv run python tests/performance/market_data_load.py
pnpm --filter web test
pnpm --filter web lint
pnpm --filter web build
uv run pytest
```

Expected: tests pass and the report records measured P50/P95/P99 freshness, throughput,
error rate, compression ratio, CPU, memory, disk, and Provider limitations.

Use `webapp-testing` to verify desktop and mobile layouts, WebSocket updates, chart
rendering, virtual scrolling, and error states with screenshots.

**Step 5: Update traceability and commit**

```bash
git add tests docs/testing/results docs/requirements/requirements-traceability-matrix.md
git commit -m "test: verify a-share market data pipeline"
```

## Final Verification

Run:

```bash
make check-workspace
make lint
make test
make build
pnpm --filter web test
pnpm --filter web lint
pnpm --filter web build
docker compose -f infra/compose/docker-compose.yml config
```

Expected: all commands PASS.

Before deployment, run the repository `fix` skill for formatting and CI checks, then
run `webapp-testing` against desktop and mobile viewports.

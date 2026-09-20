# Quant Trading SaaS Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to
> implement this plan task-by-task.

**Document ID:** QT-PLAN-001

**Goal:** 构建量化交易 SaaS 的生产级工程骨架，并交付“租户登录、模型配置、
策略标的池、Mock 行情、单股 AI 决策、确定性风控、模拟下单和审计”的首条
端到端闭环。

**Architecture:** 采用 Monorepo 管理 React Web、Python 微服务、共享契约和
基础设施。服务独占数据库 Schema，通过 REST/gRPC 与 Kafka 事件协作；
第一阶段只启动闭环所需服务，但边界与最终微服务架构一致。

**Tech Stack:** React、TypeScript、Vite、FastAPI、Pydantic v2、SQLAlchemy 2、
Alembic、MySQL 8、Redis、Kafka、MinIO/TOS、OpenTelemetry、Docker Compose、
Kubernetes/VKE、pytest、Playwright。

---

## 1. 实施原则

- 先完成 Mock 数据和模拟交易闭环，再接真实外部接口。
- 每个任务先写失败测试，再写最小实现。
- 服务不得访问其他服务数据库。
- 所有租户数据必须包含 `tenant_id`。
- 所有写接口必须支持幂等。
- 模型只生成候选决策，不能直接提交订单。
- 风控不可用时拒绝交易。
- 每个任务完成后单独提交。

## 2. 目标目录

```text
.
├── apps/
│   └── web/
├── services/
│   ├── identity-tenant/
│   ├── instrument-market/
│   ├── model-config/
│   ├── model-gateway/
│   ├── strategy/
│   ├── risk/
│   ├── trading/
│   ├── audit/
│   └── backtest/
├── packages/
│   ├── py-common/
│   ├── contracts/
│   └── ts-api-client/
├── infra/
│   ├── compose/
│   ├── helm/
│   ├── terraform/
│   └── observability/
├── tests/
│   ├── contract/
│   ├── integration/
│   └── e2e/
├── scripts/
├── Makefile
├── pnpm-workspace.yaml
└── pyproject.toml
```

## 3. 里程碑

| 里程碑 | 完成定义 |
| --- | --- |
| M1 工程底座 | 本地一条命令启动基础设施和服务模板 |
| M2 租户与模型 | 可登录并由管理员配置模型 |
| M3 策略与决策 | 标的池逐股产生结构化决策 |
| M4 模拟交易 | 决策通过风控后进入模拟撮合 |
| M5 回测 | 策略在隔离 Runner 中回测 |
| M6 外部适配 | 证券 Connector 与币安四类帐号 Scope 通过契约测试 |
| M7 生产准备 | VKE 部署、安全、性能和灾备通过 |

### Task 1: 初始化 Monorepo 与工具链

**Files:**

- Create: `pyproject.toml`
- Create: `pnpm-workspace.yaml`
- Create: `package.json`
- Create: `Makefile`
- Create: `.editorconfig`
- Create: `.gitignore`
- Create: `.pre-commit-config.yaml`
- Create: `.github/workflows/ci.yml`

#### Task 1 Step 1: 写工具链验收脚本

Create `scripts/check_workspace.sh`，检查 Python、uv、Node、pnpm、Docker，
并验证目标目录存在。缺少依赖时返回非零。

#### Task 1 Step 2: 运行并验证失败

Run: `bash scripts/check_workspace.sh`

Expected: FAIL，提示尚未创建工作区目录或缺少 pnpm。

#### Task 1 Step 3: 创建工作区配置

- Python 使用 `uv` Workspace，要求 Python 3.12。
- Node 使用 pnpm Workspace。
- 根 Makefile 提供 `bootstrap`、`lint`、`test`、`up`、`down`。
- CI 依次运行格式、静态检查、单元测试和文档检查。

#### Task 1 Step 4: 安装并验证

Run:

```bash
corepack enable
make bootstrap
make lint
```

Expected: PASS。

#### Task 1 Step 5: 提交

```bash
git add .
git commit -m "build: initialize monorepo toolchain"
```

### Task 2: 建立本地基础设施

**Files:**

- Create: `infra/compose/docker-compose.yml`
- Create: `infra/compose/.env.example`
- Create: `infra/compose/mysql/init.sql`
- Create: `infra/compose/kafka/create-topics.sh`
- Create: `scripts/wait_for_services.sh`
- Test: `tests/integration/test_infrastructure.py`

#### Task 2 Step 1: 写失败的基础设施测试

测试 MySQL、Redis、Kafka 和 MinIO 端口及健康接口。

```python
def test_mysql_is_reachable():
    assert tcp_open("127.0.0.1", 3306)
```

#### Task 2 Step 2: 验证失败

Run: `uv run pytest tests/integration/test_infrastructure.py -v`

Expected: FAIL，服务未启动。

#### Task 2 Step 3: 实现 Compose

加入 MySQL 8、Redis、Kafka、Schema Registry、MinIO 和 Mailpit。
所有密码只放在本地 `.env`，仓库仅保存 `.env.example`。

#### Task 2 Step 4: 启动并验证

Run:

```bash
make up
uv run pytest tests/integration/test_infrastructure.py -v
```

Expected: PASS。

#### Task 2 Step 5: 提交

```bash
git add infra scripts tests/integration
git commit -m "build: add local infrastructure stack"
```

### Task 3: 创建共享 Python 基础包

**Files:**

- Create: `packages/py-common/pyproject.toml`
- Create: `packages/py-common/src/qt_common/config.py`
- Create: `packages/py-common/src/qt_common/errors.py`
- Create: `packages/py-common/src/qt_common/tenant.py`
- Create: `packages/py-common/src/qt_common/idempotency.py`
- Create: `packages/py-common/src/qt_common/observability.py`
- Test: `packages/py-common/tests/`

#### Task 3 Step 1: 写租户上下文失败测试

```python
def test_tenant_context_rejects_missing_tenant():
    with pytest.raises(MissingTenantError):
        require_tenant()
```

#### Task 3 Step 2: 验证失败

Run: `uv run pytest packages/py-common/tests -v`

Expected: FAIL，模块不存在。

#### Task 3 Step 3: 实现最小公共能力

- Pydantic Settings。
- 统一错误响应。
- `ContextVar` 租户与 Trace 上下文。
- 幂等请求指纹。
- OpenTelemetry 初始化。

#### Task 3 Step 4: 验证

Run:

```bash
uv run ruff check packages/py-common
uv run mypy packages/py-common/src
uv run pytest packages/py-common/tests -v
```

Expected: PASS。

#### Task 3 Step 5: 提交

```bash
git add packages/py-common
git commit -m "feat: add shared service foundation"
```

### Task 4: 定义跨服务契约

**Files:**

- Create: `packages/contracts/asyncapi.yaml`
- Create: `packages/contracts/openapi/common.yaml`
- Create: `packages/contracts/proto/common/v1/envelope.proto`
- Create: `packages/contracts/proto/trading/v1/trading.proto`
- Create: `packages/contracts/jsonschema/model-decision-v1.json`
- Create: `scripts/generate_contracts.sh`
- Test: `tests/contract/test_schemas.py`

#### Task 4 Step 1: 写 Schema 失败测试

加载模型决策 Schema，验证未知动作和额外执行字段被拒绝。

#### Task 4 Step 2: 验证失败

Run: `uv run pytest tests/contract/test_schemas.py -v`

Expected: FAIL，Schema 不存在。

#### Task 4 Step 3: 定义契约

- `event_id`、`tenant_id`、`trace_id` 必填。
- 模型决策禁止额外字段。
- 金额和数量使用 Decimal 字符串。
- Protobuf 字段号一经发布不得复用。

#### Task 4 Step 4: 生成并验证

Run:

```bash
bash scripts/generate_contracts.sh
uv run pytest tests/contract/test_schemas.py -v
```

Expected: PASS。

#### Task 4 Step 5: 提交

```bash
git add packages/contracts scripts tests/contract
git commit -m "feat: define shared api and event contracts"
```

### Task 5: 创建 FastAPI 服务模板

**Files:**

- Create: `scripts/create_service.py`
- Create: `services/_template/pyproject.toml`
- Create: `services/_template/src/service/main.py`
- Create: `services/_template/src/service/api/health.py`
- Create: `services/_template/src/service/db.py`
- Create: `services/_template/tests/test_health.py`
- Create: `services/_template/Dockerfile`

#### Task 5 Step 1: 写模板生成测试

生成 `sample-service`，检查健康接口、配置、迁移和 Dockerfile。

#### Task 5 Step 2: 验证失败

Run: `uv run pytest scripts/tests/test_create_service.py -v`

Expected: FAIL，生成器不存在。

#### Task 5 Step 3: 实现模板

服务模板必须包含：

- `/health/live` 和 `/health/ready`。
- 租户中间件。
- 统一错误处理。
- SQLAlchemy Session。
- Alembic。
- 结构化日志和 Trace。

#### Task 5 Step 4: 验证

Run:

```bash
uv run pytest scripts/tests/test_create_service.py -v
docker build services/_template
```

Expected: PASS。

#### Task 5 Step 5: 提交

```bash
git add scripts services/_template
git commit -m "build: add fastapi service template"
```

### Task 6: 创建 Web 应用骨架

**Files:**

- Create: `apps/web/package.json`
- Create: `apps/web/src/app/router.tsx`
- Create: `apps/web/src/app/AppShell.tsx`
- Create: `apps/web/src/pages/HomePage.tsx`
- Create: `apps/web/src/pages/NewsPage.tsx`
- Create: `apps/web/src/pages/StrategiesPage.tsx`
- Create: `apps/web/src/pages/TradingPage.tsx`
- Create: `apps/web/src/pages/DataPage.tsx`
- Create: `apps/web/src/styles/tokens.css`
- Test: `apps/web/src/app/AppShell.test.tsx`

#### Task 6 Step 1: 写导航失败测试

验证首页、资讯、策略、交易、数据五个一级入口，以及租户和市场切换器。

#### Task 6 Step 2: 验证失败

Run: `pnpm --filter web test`

Expected: FAIL，应用不存在。

#### Task 6 Step 3: 实现工作台 Shell

- 使用 React Router/TanStack Router。
- 使用 Lucide 图标。
- 桌面高密度布局。
- 移动端保留监控和确认能力。
- 交易页持续显示模拟/实盘文字标识。

#### Task 6 Step 4: 验证

Run:

```bash
pnpm --filter web lint
pnpm --filter web test
pnpm --filter web build
```

Expected: PASS。

#### Task 6 Step 5: 提交

```bash
git add apps/web
git commit -m "feat: add five-workspace web shell"
```

### Task 7: 实现身份与租户服务

**Files:**

- Create: `services/identity-tenant/`
- Create: `services/identity-tenant/src/identity_tenant/models.py`
- Create: `services/identity-tenant/src/identity_tenant/auth.py`
- Create: `services/identity-tenant/src/identity_tenant/rbac.py`
- Create: `services/identity-tenant/src/identity_tenant/api/`
- Test: `services/identity-tenant/tests/`
- Test: `tests/integration/test_tenant_isolation.py`

#### Task 7 Step 1: 写失败测试

覆盖注册、登录、租户成员、五类角色、会话撤销和跨租户访问。

#### Task 7 Step 2: 验证失败

Run: `uv run pytest services/identity-tenant/tests -v`

Expected: FAIL。

#### Task 7 Step 3: 实现

- OIDC 兼容 Token。
- 密码使用 Argon2id。
- Access/Refresh Token 轮换。
- MFA 接口先提供 TOTP。
- Gateway 可验证租户与角色声明。

#### Task 7 Step 4: 验证

Run:

```bash
uv run pytest services/identity-tenant/tests -v
uv run pytest tests/integration/test_tenant_isolation.py -v
```

Expected: PASS，无跨租户数据。

#### Task 7 Step 5: 提交

```bash
git add services/identity-tenant tests/integration
git commit -m "feat: add tenant identity and rbac"
```

### Task 8: 实现审计服务

**Files:**

- Create: `services/audit/`
- Create: `services/audit/src/audit/models.py`
- Create: `services/audit/src/audit/hash_chain.py`
- Create: `services/audit/src/audit/consumer.py`
- Test: `services/audit/tests/test_hash_chain.py`

#### Task 8 Step 1: 写篡改检测测试

创建三条记录，修改中间记录后验证哈希链失败。

#### Task 8 Step 2: 验证失败

Run: `uv run pytest services/audit/tests -v`

Expected: FAIL。

#### Task 8 Step 3: 实现追加审计

- 消费 `audit.recorded.v1`。
- 记录主体、资源、前后状态引用和 Trace。
- 禁止更新与删除 API。
- 提供按租户查询。

#### Task 8 Step 4: 验证

Run: `uv run pytest services/audit/tests -v`

Expected: PASS。

#### Task 8 Step 5: 提交

```bash
git add services/audit
git commit -m "feat: add immutable audit service"
```

### Task 9: 实现模型配置服务

**Files:**

- Create: `services/model-config/`
- Create: `services/model-config/src/model_config/models.py`
- Create: `services/model-config/src/model_config/secrets.py`
- Create: `services/model-config/src/model_config/validators.py`
- Create: `services/model-config/src/model_config/api/configurations.py`
- Test: `services/model-config/tests/`

#### Task 9 Step 1: 写失败测试

覆盖：

- 只有租户管理员可写。
- API Key 不回显。
- 自定义 Base URL 阻止 SSRF。
- Ollama/vLLM 保存后为 `planned` 且不可测试。
- 被策略引用的配置不能删除。

#### Task 9 Step 2: 验证失败

Run: `uv run pytest services/model-config/tests -v`

Expected: FAIL。

#### Task 9 Step 3: 实现

先实现 `SecretBackend` 接口和本地加密 Stub；生产实现接 KMS。
数据库只保存 `secret_ref`。URL 校验必须在 DNS 解析前后都执行。

#### Task 9 Step 4: 验证

Run:

```bash
uv run pytest services/model-config/tests -v
uv run bandit -r services/model-config/src
```

Expected: PASS。

#### Task 9 Step 5: 提交

```bash
git add services/model-config
git commit -m "feat: add tenant model configuration service"
```

### Task 10: 实现模型配置 Web 页面

**Files:**

- Create: `apps/web/src/pages/settings/ModelServicesPage.tsx`
- Create: `apps/web/src/features/model-config/ModelConfigForm.tsx`
- Create: `apps/web/src/features/model-config/ModelConfigTable.tsx`
- Create: `apps/web/src/features/model-config/api.ts`
- Test: `apps/web/src/features/model-config/*.test.tsx`

#### Task 10 Step 1: 写失败测试

验证管理员可新增、测试、启停、轮换；普通成员只有模型选择权限；
Key 输入保存后不再显示。

#### Task 10 Step 2: 验证失败

Run: `pnpm --filter web test -- model-config`

Expected: FAIL。

#### Task 10 Step 3: 实现

- 类型使用下拉菜单。
- 数值使用输入或 Stepper。
- 启用使用 Toggle。
- Ollama/vLLM 显示“待开放”且禁用测试。
- 危险操作使用确认对话框。

#### Task 10 Step 4: 验证

Run:

```bash
pnpm --filter web test -- model-config
pnpm --filter web build
```

Expected: PASS。

#### Task 10 Step 5: 提交

```bash
git add apps/web
git commit -m "feat: add model services administration ui"
```

### Task 11: 实现证券主数据与 Mock 行情

**Files:**

- Create: `services/instrument-market/`
- Create: `services/instrument-market/src/instrument_market/models.py`
- Create: `services/instrument-market/src/instrument_market/providers/base.py`
- Create: `services/instrument-market/src/instrument_market/providers/mock.py`
- Create: `services/instrument-market/src/instrument_market/api/`
- Create: `services/instrument-market/fixtures/`
- Test: `services/instrument-market/tests/`

#### Task 11 Step 1: 写失败契约测试

对 A 股、港股、美股分别验证证券、日历、K 线和快照 Schema。
A 股数据按 2026-09-20 的范围基线仅包含上交所（SSE）和深交所（SZSE），
Mock 证券集与后续生产数据采用相同范围。

#### Task 11 Step 2: 验证失败

Run: `uv run pytest services/instrument-market/tests -v`

Expected: FAIL。

#### Task 11 Step 3: 实现 Provider

`MarketDataProvider` 支持标准方法，并可注入延迟、缺失、限流和故障。
所有返回值包含来源时间、采集时间、时区和币种。

#### Task 11 Step 4: 验证

Run: `uv run pytest services/instrument-market/tests -v`

Expected: PASS。

#### Task 11 Step 5: 提交

```bash
git add services/instrument-market
git commit -m "feat: add instrument master and mock market data"
```

### Task 12: 实现策略与版本服务

**Files:**

- Create: `services/strategy/`
- Create: `services/strategy/src/strategy/models.py`
- Create: `services/strategy/src/strategy/versioning.py`
- Create: `services/strategy/src/strategy/parameters.py`
- Create: `services/strategy/src/strategy/universe.py`
- Create: `services/strategy/src/strategy/api/`
- Test: `services/strategy/tests/`

#### Task 12 Step 1: 写失败测试

覆盖草稿、JSON Schema 参数、CSV 标的池、发布不可变版本和生命周期。

#### Task 12 Step 2: 验证失败

Run: `uv run pytest services/strategy/tests -v`

Expected: FAIL。

#### Task 12 Step 3: 实现

- 源码存对象存储，数据库保存引用和校验和。
- 发布时冻结参数、标的池、模型配置和提示词。
- 自动实盘不得跳过状态。

#### Task 12 Step 4: 验证

Run: `uv run pytest services/strategy/tests -v`

Expected: PASS。

#### Task 12 Step 5: 提交

```bash
git add services/strategy
git commit -m "feat: add strategy lifecycle and versioning"
```

### Task 13: 实现模型网关与结构化决策

**Files:**

- Create: `services/model-gateway/`
- Create: `services/model-gateway/src/model_gateway/providers/base.py`
- Create: `services/model-gateway/src/model_gateway/providers/openai.py`
- Create: `services/model-gateway/src/model_gateway/providers/anthropic.py`
- Create: `services/model-gateway/src/model_gateway/providers/deepseek.py`
- Create: `services/model-gateway/src/model_gateway/providers/openai_compatible.py`
- Create: `services/model-gateway/src/model_gateway/decision.py`
- Test: `services/model-gateway/tests/`

#### Task 13 Step 1: 写失败测试

Stub 分别返回合法、非法、超时、429、矛盾和额外字段响应。

#### Task 13 Step 2: 验证失败

Run: `uv run pytest services/model-gateway/tests -v`

Expected: FAIL。

#### Task 13 Step 3: 实现

- 读取 Model Config 的非敏感配置及短期 Secret。
- 强制 JSON Schema。
- 非法结果统一转换为 `hold`。
- 保存输入输出到隔离对象路径。
- 记录 Token、费用、耗时和错误码。

#### Task 13 Step 4: 验证

Run: `uv run pytest services/model-gateway/tests -v`

Expected: PASS。

#### Task 13 Step 5: 提交

```bash
git add services/model-gateway
git commit -m "feat: add structured llm decision gateway"
```

### Task 14: 实现逐股分析编排

**Files:**

- Create: `services/strategy/src/strategy/analysis.py`
- Create: `services/strategy/src/strategy/triggers.py`
- Create: `services/strategy/src/strategy/outbox.py`
- Test: `services/strategy/tests/test_analysis.py`
- Test: `tests/integration/test_analysis_flow.py`

#### Task 14 Step 1: 写失败测试

10 只股票产生 10 个独立任务；重复事件只调用一次；过期行情不调用模型。

#### Task 14 Step 2: 验证失败

Run: `uv run pytest tests/integration/test_analysis_flow.py -v`

Expected: FAIL。

#### Task 14 Step 3: 实现

- 定时与行情事件统一转换为分析请求。
- 使用稳定幂等键。
- 校验冷却、调用次数、并发和费用预算。
- 输入快照使用同一市场时点。

#### Task 14 Step 4: 验证

Run:

```bash
uv run pytest services/strategy/tests -v
uv run pytest tests/integration/test_analysis_flow.py -v
```

Expected: PASS。

#### Task 14 Step 5: 提交

```bash
git add services/strategy tests/integration
git commit -m "feat: orchestrate per-symbol model analysis"
```

### Task 15: 实现组合协调与风控

**Files:**

- Create: `services/risk/`
- Create: `services/risk/src/risk/models.py`
- Create: `services/risk/src/risk/rules.py`
- Create: `services/risk/src/risk/portfolio.py`
- Create: `services/risk/src/risk/api/evaluate.py`
- Test: `services/risk/tests/`

#### Task 15 Step 1: 写失败属性测试

随机生成买入决策，验证总批准金额不超过现金、仓位和集中度限制。

#### Task 15 Step 2: 验证失败

Run: `uv run pytest services/risk/tests -v`

Expected: FAIL。

#### Task 15 Step 3: 实现

实现权限、时段、标的、资金、持仓、价格偏离、频率、敞口、亏损、
置信度、新鲜度和五级急停。服务异常时调用方 Fail closed。

#### Task 15 Step 4: 验证

Run: `uv run pytest services/risk/tests -v`

Expected: PASS。

#### Task 15 Step 5: 提交

```bash
git add services/risk
git commit -m "feat: add portfolio coordination and deterministic risk"
```

### Task 16: 实现交易状态机与模拟撮合

**Files:**

- Create: `services/trading/`
- Create: `services/trading/src/trading/models.py`
- Create: `services/trading/src/trading/state_machine.py`
- Create: `services/trading/src/trading/idempotency.py`
- Create: `services/trading/src/trading/simulator.py`
- Create: `services/trading/src/trading/ledger.py`
- Create: `services/trading/src/trading/api/`
- Test: `services/trading/tests/`

#### Task 16 Step 1: 写失败测试

覆盖幂等并发、合法/非法状态转移、部分成交、撤单、资金与账本不变量。

#### Task 16 Step 2: 验证失败

Run: `uv run pytest services/trading/tests -v`

Expected: FAIL。

#### Task 16 Step 3: 实现

- 订单状态机使用显式转移表。
- 同一幂等键只创建一个订单。
- 模拟撮合支持市价、限价、滑点、手续费和部分成交。
- 账本使用不可变分录并保持借贷平衡。

#### Task 16 Step 4: 验证

Run: `uv run pytest services/trading/tests -v`

Expected: PASS。

#### Task 16 Step 5: 提交

```bash
git add services/trading
git commit -m "feat: add trading state machine and simulation"
```

### Task 17: 打通首条端到端闭环

**Files:**

- Create: `tests/e2e/test_strategy_to_simulated_order.py`
- Create: `tests/e2e/fixtures/`
- Modify: `infra/compose/docker-compose.yml`
- Modify: `Makefile`

#### Task 17 Step 1: 写失败 E2E 测试

测试流程：

1. 创建租户管理员。
2. 配置 Mock OpenAI Compatible。
3. 创建策略和三只股票标的池。
4. 触发分析。
5. 生成逐股决策。
6. 风控拒绝一只、观望一只、批准一只。
7. 模拟成交。
8. 验证审计链。

#### Task 17 Step 2: 验证失败

Run: `uv run pytest tests/e2e/test_strategy_to_simulated_order.py -v`

Expected: FAIL，服务尚未完整编排。

#### Task 17 Step 3: 补齐编排

只修复闭环所需集成，不增加未进入验收范围的抽象。

#### Task 17 Step 4: 验证

Run:

```bash
make up
uv run pytest tests/e2e/test_strategy_to_simulated_order.py -v
make test
```

Expected: 全部 PASS。

#### Task 17 Step 5: 提交

```bash
git add .
git commit -m "feat: complete strategy to simulated order flow"
```

### Task 18: 实现策略与交易 Web 工作流

**Files:**

- Create: `apps/web/src/pages/strategies/StrategyEditorPage.tsx`
- Create: `apps/web/src/features/strategies/UniverseEditor.tsx`
- Create: `apps/web/src/features/strategies/ParameterEditor.tsx`
- Create: `apps/web/src/features/strategies/ModelSelector.tsx`
- Create: `apps/web/src/pages/trading/SimulationPage.tsx`
- Create: `apps/web/src/pages/trading/LiveTradingPage.tsx`
- Create: `apps/web/src/pages/trading/CnTradingPage.tsx`
- Create: `apps/web/src/pages/trading/HkUsTradingPage.tsx`
- Create: `apps/web/src/pages/trading/BinanceTradingPage.tsx`
- Create: `apps/web/src/features/trading/AccountBindingDialog.tsx`
- Create: `apps/web/src/features/trading/OrderTicket.tsx`
- Test: `apps/web/src/features/**/*.test.tsx`
- Test: `tests/e2e/web/strategy-trading.spec.ts`

#### Task 18 Step 1: 写失败测试

验证创建策略、导入标的、选模型、触发分析、确认信号、三个交易子页面、
通道白名单、添加帐号和查看模拟成交。

#### Task 18 Step 2: 验证失败

Run: `pnpm --filter web test`

Expected: FAIL。

#### Task 18 Step 3: 实现

- Monaco 编辑器。
- 参数表单由 JSON Schema 生成。
- 模型只显示租户已启用配置。
- 交易页面固定提供沪深、港美、币安三个二级入口。
- 每个交易页面右上角提供“添加帐号”，并限制可选通道。
- 币安页面提供现货、全仓、逐仓和 U 本位产品标签。
- 交易页面固定显示环境、帐号 Scope 和连接状态。
- 自动交易开关要求确认。

#### Task 18 Step 4: 验证

Run:

```bash
pnpm --filter web test
pnpm --filter web build
pnpm exec playwright test tests/e2e/web/strategy-trading.spec.ts
```

Expected: PASS，无文本重叠和环境混淆。

#### Task 18 Step 5: 提交

```bash
git add apps/web tests/e2e/web
git commit -m "feat: add strategy and simulation workspaces"
```

### Task 19: 实现回测调度与沙箱 Runner

**Files:**

- Create: `services/backtest/`
- Create: `services/backtest/src/backtest/scheduler.py`
- Create: `services/backtest/src/backtest/runner.py`
- Create: `services/backtest/src/backtest/results.py`
- Create: `services/backtest/images/runner/Dockerfile`
- Create: `infra/compose/backtest-network-policy.yaml`
- Test: `services/backtest/tests/`
- Test: `tests/integration/test_backtest_sandbox.py`

#### Task 19 Step 1: 写失败测试

验证可复现、超时、内存限制、无外网和跨任务文件隔离。

#### Task 19 Step 2: 验证失败

Run: `uv run pytest tests/integration/test_backtest_sandbox.py -v`

Expected: FAIL。

#### Task 19 Step 3: 实现

本地使用受限容器模拟 Kubernetes Job；生产使用非 root、只读文件系统、
Seccomp、NetworkPolicy 和资源限制。

#### Task 19 Step 4: 验证

Run:

```bash
uv run pytest services/backtest/tests -v
uv run pytest tests/integration/test_backtest_sandbox.py -v
```

Expected: PASS。

#### Task 19 Step 5: 提交

```bash
git add services/backtest infra tests/integration
git commit -m "feat: add isolated backtest execution"
```

### Task 20: 定义 BrokerAdapter 与五个 Stub Connector

**Files:**

- Create: `packages/py-common/src/qt_common/broker.py`
- Create: `services/broker-connectors/futu/`
- Create: `services/broker-connectors/longbridge/`
- Create: `services/broker-connectors/tonghuashun-sim/`
- Create: `services/broker-connectors/caixin/`
- Create: `services/broker-connectors/binance/`
- Create: `tests/contract/brokers/test_broker_contract.py`

#### Task 20 Step 1: 写统一契约测试

覆盖连接、账户、资金、持仓、下单、撤单、查询、回报和对账。币安额外覆盖
现货、全仓杠杆、逐仓杠杆、U 本位永续、借还款和强平保护。

#### Task 20 Step 2: 验证失败

Run: `uv run pytest tests/contract/brokers -v`

Expected: FAIL。

#### Task 20 Step 3: 实现可控 Stub

Stub 支持正常、拒单、部分成交、断连、超时、重复回报和未知状态。
真实 Adapter 必须复用同一契约。

#### Task 20 Step 4: 验证

Run: `uv run pytest tests/contract/brokers -v`

Expected: 五个 Stub 全部 PASS。

#### Task 20 Step 5: 提交

```bash
git add packages/py-common services/broker-connectors tests/contract
git commit -m "feat: add broker adapter contract and stubs"
```

### Task 21: 接入真实外部测试环境

**Files:**

- Modify: `services/broker-connectors/futu/`
- Modify: `services/broker-connectors/longbridge/`
- Modify: `services/broker-connectors/tonghuashun-sim/`
- Modify: `services/broker-connectors/caixin/`
- Modify: `services/broker-connectors/binance/`
- Create: `docs/integrations/capability-matrix.md`
- Create: `docs/integrations/integration-test-report-template.md`

#### Task 21 Step 1: 确认前置条件

必须已有官方协议、测试账号、正式文档和授权结论。任何一项缺失时，
该 Connector 保持 Stub，任务状态标记 Blocked，不自行逆向。

币安还必须准备固定出口 IP、KMS、生产只读 Key、现货/杠杆/U 本位资格和
书面合规结论；检测到提现权限时立即阻断。

#### Task 21 Step 2: 为每个真实接口运行契约测试

Run:

```bash
uv run pytest tests/contract/brokers \
  --broker=futu-test \
  --broker=longbridge-test \
  --broker=tonghuashun-sim-test \
  --broker=caixin-test \
  --broker=binance-testnet
```

Expected: 按能力矩阵通过；不支持能力明确 Skip 并附证据。

#### Task 21 Step 3: 运行故障和对账测试

验证断连、超时、重连、重复回报、未知订单和账实差异。币安额外验证 API
限频、时间偏差、流失效、借还款待处理、预强平、强平和 ADL 风险。

#### Task 21 Step 4: 生成联调报告

记录版本、账号类型、接口限制、已知问题和生产准入条件。

#### Task 21 Step 5: 分通道提交

```bash
git commit -m "feat: integrate futu test connector"
git commit -m "feat: integrate longbridge test connector"
git commit -m "feat: integrate tonghuashun simulation connector"
git commit -m "feat: integrate caixin test connector"
git commit -m "feat: integrate binance connector"
```

币安生产灰度按只读、最小金额现货、全仓、逐仓、U 本位顺序独立审批；
每阶段完成对账后才允许进入下一阶段。

### Task 22: 建立 Kubernetes 与火山引擎部署

**Files:**

- Create: `infra/helm/platform/`
- Create: `infra/helm/services/`
- Create: `infra/terraform/modules/`
- Create: `infra/terraform/environments/dev/`
- Create: `infra/terraform/environments/staging/`
- Create: `infra/terraform/environments/prod/`
- Test: `tests/infrastructure/`

#### Task 22 Step 1: 写 IaC 验证

检查命名空间、NetworkPolicy、Pod 安全、资源限制、跨可用区和 Secret 引用。

#### Task 22 Step 2: 验证失败

Run:

```bash
helm lint infra/helm/platform
terraform -chdir=infra/terraform/environments/dev validate
```

Expected: FAIL，模板不存在。

#### Task 22 Step 3: 实现

- Dev/Staging/Prod 物理隔离。
- Connector 与 Runner 独立节点池。
- KMS、TOS、MySQL、Redis、Kafka 使用托管服务。
- 禁止在 Values 中保存密钥。

#### Task 22 Step 4: 验证

Run:

```bash
helm lint infra/helm/platform
terraform -chdir=infra/terraform/environments/dev validate
uv run pytest tests/infrastructure -v
```

Expected: PASS。

#### Task 22 Step 5: 提交

```bash
git add infra tests/infrastructure
git commit -m "infra: add volcano engine deployment"
```

### Task 23: 完成生产准入验证

**Files:**

- Create: `tests/performance/`
- Create: `tests/security/`
- Create: `tests/chaos/`
- Create: `docs/reports/release-readiness-template.md`
- Modify: `docs/requirements/requirements-traceability-matrix.md`

#### Task 23 Step 1: 自动化关键 NFR

- 查询 P95 <= 500 ms。
- 风控 P95 <= 300 ms。
- 触发入队 P95 <= 1 秒。
- 订单事件零丢失。
- 租户隔离零失败。

#### Task 23 Step 2: 运行安全与故障演练

Run:

```bash
make test-security
make test-performance
make test-chaos
```

Expected: 全部达到文档基线。

#### Task 23 Step 3: 执行备份和灾备

验证 RPO <= 5 分钟、RTO <= 30 分钟；恢复后先对账，再恢复自动交易。

#### Task 23 Step 4: 更新追踪矩阵

将已实现并验证的需求状态改为 `Verified`，Blocked 外部依赖保留证据链接。

#### Task 23 Step 5: 提交

```bash
git add tests docs
git commit -m "test: add production readiness verification"
```

## 4. 每个里程碑的统一验收

Run:

```bash
make lint
make test
make test-contract
make test-integration
pnpm --filter web build
```

Expected:

- 无格式、类型和安全扫描错误。
- 所有单元与契约测试通过。
- 不存在跨服务数据库访问。
- 不存在明文密钥。
- 文档和 Schema 与实现同步。

## 5. 外部工作流

工程实施同时推进：

1. 富途 OpenAPI 申请与测试环境。
2. 同花顺模拟盘商务和技术确认。
3. 财信证券正式量化通道确认。
4. 长桥 OpenAPI 申请与测试环境。
5. 币安生产现货、全仓/逐仓杠杆和 U 本位永续帐号资格。
6. 币安固定出口 IP、Ed25519 Key、KMS 和只读联调。
7. 行情与资讯数据授权采购。
8. 法务、合规、税务和隐私评审。

外部依赖不得阻塞 Mock 闭环，但会阻塞真实通道生产验收。
币安生产接入按
[`QT-DES-TRD-001`](2026-09-19-trading-account-and-binance-integration-design.md)
拆分后续实现任务，完成只读同步和小额人工灰度前不得启用自动交易。

## 6. 首次执行建议

第一批执行 Task 1 至 Task 6，完成工程底座和五大菜单 Shell。
第二批执行 Task 7 至 Task 10，完成租户和模型配置。
第三批执行 Task 11 至 Task 18，完成首条模拟交易闭环。

每批结束后进行代码审查、威胁模型复核和演示，不跨批积累未验证变更。

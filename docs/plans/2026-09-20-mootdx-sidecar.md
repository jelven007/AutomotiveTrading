# Mootdx Sidecar Implementation Plan

<!-- markdownlint-disable MD013 MD032 MD036 -->

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.
>
> 当前环境未安装上述子技能；按本文件逐项实施和验证。用户已授权“实现隔离采集 Sidecar 并接入真实全市场采集”，沿用已有需求基线，无需再次审批。

**Goal:** 部署独立 mootdx 采集进程，将实际可获取的沪深北 A 股快照持续保存，输出真实覆盖、缺口和源时间质量。

**Architecture:** 独立 Python 项目、锁文件和容器隔离 mootdx/httpx 0.25；每个工作线程独占行情连接，显式传入市场编号。原始响应先写本地持久队列，再通过带内部令牌的 HTTP 批量发送到 instrument-market，后者写入 ClickHouse；证券快照、逐轮覆盖和待发送状态均可恢复。

**Tech Stack:** Python 3.12、mootdx 0.11.7、tdxpy、httpx 0.25 / 0.28、SQLite WAL、FastAPI、MySQL、ClickHouse、Docker Compose、pytest。

---

## 1. 范围、决策与验收口径

需求依据：

- `docs/requirements/a-share-market-data-requirements.md` 中 FR-CNMD-001~006、008、018、022 的快照采集部分。
- `docs/plans/2026-09-20-a-share-market-data-design.md` 的独立 Sidecar、原始保留、明确缺口原则。
- `docs/testing/a-share-market-data-test-plan.md` 的 Provider、重启、部分覆盖和源时间测试。

本阶段交付证券枚举、全市场快照轮询、可靠待发送队列、核心接收改进和部署。K 线仅用于辅助判定源交易日；历史回填、分笔、F10、完整 Tushare 对账、Redis/WebSocket 和新前端页面仍按总计划推进。

比较三种接入：

1. **持久队列 + 内部 HTTP（采用）**：复用当前接口，先落盘再发送，进程重启可重试，当前阶段故障面较小。
2. 直接引入 Kafka 生产者/消费者：适合后续多数据集流水线，但需要同时完成消费、归档和检查点体系。
3. 内存 HTTP 转发：无法恢复采集后网络故障，不采用。

持久队列使用 SQLite 的 WAL 模式和 `synchronous=FULL`，保存原始请求压缩内容、批次 ID、状态、重试时间和检查点。确认成功后保留原始内容，不自动清理历史。达到配置的磁盘/队列阈值时停止新采集并暴露状态。此阶段本地原始保留不等同于已完成 MinIO 长期归档。

## 2. Provider 与证券范围

- 固定使用 PyPI 发行版，独立 `uv.lock`；根 workspace 显式排除服务目录。
- mootdx 高层自动映射尚未识别北交所 `920` 代码，因此通过 mootdx 创建的连接调用其底层显式 `(market, code)` 接口，避免 DataFrame 再次转换数字。
- 标准市场编号：SZSE=0、SSE=1、BSE=2。证券列表分页按实际返回数推进，遇到空页/重复页/数量变化生成不完整状态。
- 沪市仅纳入 600/601/603/605/688/689；深市纳入 000/001/002/003/300/301；北市识别 920 及旧 43/83/87/88 代码，且保留“候选范围未核验”状态，不能将整个新三板视为北交所。
- 如配置 Tushare Token，读取 `stock_basic(list_status=L)` 校准证券全集和交易所；无 Token 时保留 TDX 候选范围及 `unverified`，不声称权威全市场覆盖已经通过。
- 保存每次证券同步的原始分页、规范证券列表、同步时间、来源和各市场缺口。刷新失败继续使用最后一个可用快照，并展示过期状态。
- 默认从依赖提供的候选节点中有界测速；测速要求实际行情响应，不以 TCP 连接成功作为节点健康。节点地址不出现在公开报告，使用稳定哈希别名。
- 每个连接设置超时、禁用库内无限/隐式重试；有限次数失败后换节点。mootdx 全局配置初始化和连接构造串行，工作线程不共享 socket。

## 3. 快照、时间与单位

- 每批不超过 80 只，每个批次只属于一个交易所；工作线程数默认 8、最大 16。
- 每轮记录 expected / received / missing / unexpected / duplicates、采集耗时、节点切换和每市场统计；收集到行情和已送达核心分别计数。
- 2 秒轮询为调度目标，超时不叠加无限任务；闭市降低频率，工作日午间暂停高频轮询。
- 通过最新日 K 获取候选源交易日，不把周末采集日期强写成行情日期。行情的 `servertime` 只有时分秒，不带交易日，推定的日期必须记录依据。
- 核心支持 `HH:MM:SS[.fff]`。时间缺失、解析失败、仅推定日期、未来时间、价格无效和过期状态必须显式标记，不作为 `healthy` 行情。
- 原始数据保留上游解析值。tdxpy 本身返回浮点价格，标准化用 Decimal 和证券精度处理，不能宣称从网络到存储从未经过浮点。
- 证券列表提供 `volunit`；A 股快照成交量、盘口量在标准层按该单位换算为股，原始层保持源值。未知单位不得默认已校验。
- 现有服务没有对接策略行情读取；本阶段不改变真实交易开关。

## 4. 发送与核心持久化

- 数据库事务提交原始批次后才允许 HTTP 发送。批次 ID 在重试期间不变。
- 仅在 HTTP 成功且应答批次/接受条数符合契约时确认；网络错误和 5xx 有界退避，鉴权/格式错误保留批次并告警，不能丢弃或忙循环。
- 退出时停止新任务，等待有界采集完成并保存结果；启动先恢复待发送记录。
- 核心在处理非法行之前保留整个原始批次；单条坏数据不能阻断同批其余证券。
- 增加持久接收凭证/批次哈希检查；相同 ID 不同内容返回 409，成功批次重试返回相同结果。
- 原始事件 ID 按 batch_id + 行号确定，支持故障重放时按事件逻辑去重。ClickHouse 与关系库没有分布式事务，不能承诺跨存储物理恰好一次。
- 保留批次、原始响应、source_id、时间依据、单位和质量原因，人工核验可从核心数据追踪到 Sidecar 原始批次。
- 内部证券/覆盖状态上报复用内部令牌；公开 liveness 不带敏感状态，详细状态需鉴权。

## 5. 实施步骤

### Task 1: 隔离环境与 Provider

**Files:** 新建 `services/mootdx-collector/pyproject.toml`、`uv.lock`、`src/mootdx_collector/config.py`、`provider.py`、`universe.py`；修改根 `pyproject.toml`。

1. 准备 Python 单测流程，输出 TARGETS 和缺陷映射。
2. 编写证券分类、920 市场路由、分页、超时/换节点和配置边界测试。
3. 验证测试红灯，实现独立环境、连接池、证券枚举与可选 Tushare 对照。
4. 执行 `uv run --project services/mootdx-collector pytest tests/test_provider.py tests/test_universe.py -v`。

### Task 2: 原始队列与采集循环

**Files:** 新建 `src/mootdx_collector/spool.py`、`transport.py`、`collector.py`、`__main__.py`。

1. 测试先落盘、失败后重启恢复、批次不变、鉴权失败退避、磁盘阈值及部分覆盖。
2. 实现 SQLite 原始保留、有限发送、每交易所分片、单轮/持续运行、交易时间调度。
3. 提供 `python -m mootdx_collector once`、`run`、`status` 命令；单轮输出 JSON 汇总和持久化报告。
4. 执行 `uv run --project services/mootdx-collector pytest -v`。

### Task 3: 接收与质量

**Files:** 修改 `services/instrument-market/src/instrument_market/api/ingestion.py`、`services/quotes.py`、`pipeline/normalize.py`、`pipeline/quality.py`、`storage/clickhouse.py`；按需要新增接收凭证、内部状态接口和迁移。

1. 对毫秒源时间、未知日期/单位、重放延迟、非法行和重复批次编写回归测试。
2. 实现原始优先、行级拒绝、元数据和持久接收状态。
3. 测试同批次重复/冲突，以及标准写入失败后的恢复。
4. 执行 `uv run pytest services/instrument-market/tests tests/contract -v`。

### Task 4: 部署与真实验收

**Files:** 新建 Sidecar `Dockerfile`、`.env.example`、`README.md`；修改 `infra/compose/docker-compose.deploy.yml`、两个 env 示例、`scripts/deploy.sh`；新增 `docs/testing/results/mootdx-sidecar-acceptance.md`。

1. 接入独立镜像、持久卷、健康检查、资源限制及与核心一致的内部令牌。
2. 检查旧部署配置的增量升级；仅重建本次涉及的业务容器，使用 `--no-deps` 保留现有基础组件运行。
3. 执行离线测试、Ruff、契约、Compose config 和脚本检查。
4. 真实运行一轮沪深北采集，核对证券全集来源、原始行数、标准行数、质量和缺口。
5. 核验重复发送和重启恢复，启动持续采集；记录日期、耗时、实际覆盖和未验收事项。
6. 提交代码与文档，合并回当前工作区；不自动推送或部署 ECS。

## 6. 测试与交付标准

| 场景 | 必须符合的结果 |
| --- | --- |
| 依赖隔离 | 根 httpx 仍为 0.28；Sidecar 为 0.25；各自锁文件可重建 |
| 市场路由 | 600/000/920 分别发送到 1/0/2；不依赖 mootdx 自动猜测 |
| 分页与部分响应 | 不跳页、不把空响应算成功，缺失代码可查 |
| 重启/断网 | 已落盘数据保留，重发使用原 ID，错误应答不确认 |
| 原始追踪 | 响应所有字段保留，包括暂不理解的字段 |
| 时间与单位 | 毫秒可解析，周末不伪造当天时间，未知信息不能标 healthy |
| 安全与资源 | Token 不进日志，内部 API 不公开，无限并发/重试被禁止 |
| 真实验证 | 记录真实返回数量，不用人工夹具替代；无节点可用须留证据 |
| 延迟 | 周末仅验接入；交易时段 P95 3 秒和五日稳定性仍单独验收 |

遇到上游网络或权限限制，继续完成可离线验证的实现和运行状态输出；准确列出无法完成的真实验收及所需外部条件。

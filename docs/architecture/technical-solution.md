# 量化交易 SaaS 技术方案

> 文档编号：QT-TDS-001
>
> 版本：1.3-draft

## 1. 架构目标

系统采用领域微服务与事件驱动架构，重点保证租户隔离、交易安全、
异步计算弹性、外部适配能力和全链路审计。

## 2. 技术栈

| 层次 | 选型 |
| --- | --- |
| Web | React、TypeScript、Vite、TanStack Query/Router |
| 图表 | Lightweight Charts、ECharts |
| 编辑器 | Monaco Editor |
| API Gateway | Kong 或 APISIX |
| 业务服务 | Python 3.12、FastAPI、Pydantic |
| 内部 RPC | gRPC、Protobuf |
| 事务数据 | MySQL 8 |
| 分析数据 | ClickHouse |
| 缓存/锁 | Redis |
| 消息 | Kafka |
| 对象存储 | 火山引擎 TOS |
| 容器编排 | Kubernetes/VKE |
| 可观测性 | OpenTelemetry、Prometheus、Grafana、Loki/云日志 |
| 密钥 | 火山引擎 KMS/密钥管理 |

## 3. 服务划分

| 服务 | 数据所有权 | 主要职责 |
| --- | --- | --- |
| identity-tenant | 用户、租户、角色、会话 | 登录、MFA、RBAC、租户上下文 |
| subscription-billing | 套餐、权益、用量 | 配额校验、计量和账单 |
| instrument | 证券、数字资产、市场、交易日历、映射 | 多市场标准主数据 |
| market-data | 行情元数据与采集任务 | Provider、标准化、查询和推送 |
| news | 资讯与关联 | 采集、去重、标签、快照 |
| strategy | 策略、源码、版本、参数 | 策略生命周期 |
| trigger | 触发配置与执行记录 | 定时和行情事件触发 |
| model-config | 模型配置与密钥引用 | 供应商、模型、权限、健康状态 |
| model-gateway | 模型调用与决策原始记录 | 路由、限流、Schema 校验、计费 |
| portfolio | 候选决策与组合结果 | 资金和敞口协调 |
| backtest-scheduler | 回测任务 | 配额、调度和状态 |
| backtest-runner | 无长期业务数据 | 沙箱执行 |
| risk | 风控策略和校验记录 | 确定性交易风控 |
| trading | 账户镜像、订单、成交、账本 | 交易核心状态机 |
| broker-connectors | 连接、签名与外部状态 | 富途、长桥、同花顺、财信、币安 |
| reconciliation | 对账任务和差异 | 账户一致性 |
| notification | 通知模板与投递 | 站内、邮件、短信、Webhook |
| audit | 不可变审计记录 | 安全和业务审计 |

### 3.1 A 股行情专项实现

A 股行情范围按 2026-09-20 确认限定为上交所（SSE）和深交所（SZSE）。
“全市场”及覆盖统计仅指沪深；北交所不作为采集、补齐或验收对象。

该子域由 `instrument-market` 核心服务和隔离的 mootdx 采集 Sidecar
共同承载。Sidecar 使用 mootdx 的 `Quotes`、`Reader` 和 `Affair` 三类通道
获取沪深范围内可提供的全部数据，通过内部鉴权接口或 Kafka 发送到核心服务；
Tushare 用于沪深主数据补充、历史数据回补和日终交叉校验，证券名单须先筛选 SSE/SZSE。

mootdx 0.11.7 固定依赖 `httpx < 0.26`，因此不得与平台统一使用
`httpx 0.28` 的核心服务安装在同一 Python 环境。

数据按职责写入：

- MySQL：证券主数据、Provider 能力、任务、游标和质量事件。
- ClickHouse：实时快照、分笔、K 线、财务指标和历史版本。
- MinIO：不可变原始响应、TDX 文件、财务文件、F10 原文和 Parquet。
- Redis：最新行情与短期推送状态。
- Kafka/Redpanda：采集与持久化之间的可重放事件缓冲。

详细设计、能力边界和前端交互见
[`QT-DES-CNMD-001`](../plans/2026-09-20-a-share-market-data-design.md)。

## 4. 核心链路

### 4.1 AI 策略链路

1. Trigger Service 产生 `strategy.analysis.requested.v1`。
2. Market Data、News、Trading 提供时点快照。
3. Model Gateway 加载租户模型配置并调用模型。
4. JSON Schema 校验失败则生成 `hold`。
5. Portfolio Coordinator 处理组合冲突。
6. Risk Service 进行确定性校验。
7. 人工模式进入待确认；自动模式生成订单请求。
8. Trading Service 路由到模拟撮合或 Connector。
9. 全过程写入 Audit Service。

### 4.2 订单链路

1. API Gateway 校验身份、租户、MFA 和幂等键。
2. Trading 创建 `created` 订单。
3. Risk 返回通过或拒绝。
4. Trading 以 Outbox 发布提交事件。
5. Connector 按现货、杠杆或合约产品归一化请求，调用券商/交易所并保存
   原始结果摘要。
6. 券商/交易所推送或轮询更新订单状态。
7. Trading 更新账本、持仓和资金镜像。
8. Reconciliation 定时校验券商/交易所实际状态。

### 4.3 回测链路

1. Strategy 发布不可变版本。
2. Scheduler 校验权益、配额和数据可用性。
3. 创建 Kubernetes Job。
4. Runner 只读加载输入，输出写入隔离路径。
5. Scheduler 计算摘要并发布完成事件。
6. WebSocket 推送进度和结果。

## 5. 一致性设计

- 服务独占数据库 Schema。
- 本地事务与 Outbox 同时提交。
- 消费者按 `event_id` 幂等。
- 不使用跨服务数据库事务。
- 订单、成交和账本采用不可变事件及派生快照。
- 资金与持仓以券商为最终外部事实，对账差异显式处理。

## 6. 租户隔离

- Gateway 从 Token 提取租户，不接受客户端任意覆盖。
- 服务层查询必须包含 `tenant_id`。
- 数据库唯一索引包含 `tenant_id`。
- Redis Key 使用租户前缀。
- Kafka 事件包含租户并在消费者再次校验。
- TOS 使用独立租户前缀和短期签名 URL。
- 管理员跨租户操作使用独立审计权限。

## 7. 模型配置架构

模型配置分为四层：

1. Provider Type：OpenAI、Anthropic、DeepSeek、OpenAI Compatible、
   Ollama、vLLM。
2. Credential：KMS Secret 引用，不保存明文。
3. Model Endpoint：Base URL、Model ID、能力和状态。
4. Runtime Profile：采样参数、超时、重试、并发、预算和环境权限。

一期运行状态：

| 类型 | 保存 | 字段校验 | 连接测试 | 策略调用 |
| --- | --- | --- | --- | --- |
| OpenAI | 是 | 是 | 是 | 是 |
| Anthropic | 是 | 是 | 是 | 是 |
| DeepSeek | 是 | 是 | 是 | 是 |
| OpenAI Compatible | 是 | 是 | 是 | 是 |
| Ollama | 是 | 是 | 否 | 否 |
| vLLM | 是 | 是 | 否 | 否 |

## 8. 币安 Connector 架构

币安生产接入使用独立 Connector，不允许 Web、策略或 Trading Service
直接访问币安 API。Connector 内部分为：

1. Credential Provider：按租户和帐号从 KMS 临时解密 Ed25519 私钥、
   HMAC Secret 或 RSA 私钥，不写入磁盘。
2. Time Sync：持续校准币安服务器时间，签名请求默认
   `recvWindow <= 5000 ms`。
3. Spot Client：账户、余额、订单、成交和现货交易。
4. Margin Client：全仓/逐仓账户、划转、借还款、负债、利息和杠杆订单。
5. USD-M Futures Client：账户、持仓、保证金模式、杠杆、订单、成交和
   资金费率。
6. Stream Supervisor：维护用户数据流，检测序列中断并触发 REST 补偿。
7. Rate Limit Governor：按 IP、UID、订单窗口和接口权重限流。

统一帐号下按 `spot`、`cross_margin`、`isolated_margin` 和
`usdm_futures` 建立四类 `account_scope`。所有写请求先进入 Trading
状态机和 Risk Service，再由 Connector 生成币安 `clientOrderId`；
网络超时返回 `unknown`，只能查询确认，不得直接重发。

杠杆和合约额外规则：

- 借款、还款和划转使用独立幂等流水，串行处理币安返回的待处理状态。
- 全仓与逐仓风险快照分开存储，逐仓快照必须包含交易对。
- 合约下单前同步单向/双向持仓模式、全仓/逐仓保证金模式和杠杆倍数。
- 保护模式只允许撤单、还款、追加保证金和 `reduceOnly` 减仓。
- 币本位合约、期权和未声明产品由能力矩阵直接拒绝。

## 9. 网络与安全边界

- 公网入口只开放 WAF 和 Gateway。
- 服务位于私有子网。
- Broker Connector 使用独立命名空间、节点池和出口白名单。
- 币安生产 Key 必须配置固定出口 IP 白名单，禁止提现权限。
- 币安查询权限和交易权限分别校验；生产写权限默认关闭。
- Backtest Runner 默认无网络策略。
- 模型调用只能由 Model Gateway 发起。
- KMS 权限按服务身份授予，业务数据库只保存 Secret ID。
- 生产访问通过堡垒机、短期身份和审批。

## 10. 故障与降级

- Market Data 异常：停止新分析或返回观望。
- Model Provider 异常：按策略允许的备用模型降级，否则观望。
- Risk 异常：Fail closed。
- Broker 异常：禁止新订单，保留撤单与减仓。
- 币安用户数据流异常：切换 REST 补偿并暂停新增风险，恢复后先对账。
- 杠杆/合约进入追加保证金、预强平或强平状态：强制进入保护模式。
- Kafka 异常：本地 Outbox 持久化，不确认未落盘事件。
- ClickHouse 异常：交易主链路继续，分析查询降级。
- Audit 异常：高风险操作无法可靠缓冲时拒绝。

## 11. 扩展性

- Provider、模型和券商均以 Adapter 接入。
- OpenAPI、Protobuf 和事件 Schema 版本化。
- 每个服务可独立扩容。
- 行情推送按标的分区。
- 模型任务按租户和策略公平调度。
- 回测使用按任务弹性创建的计算资源。

## 12. 架构决策记录

| ADR | 决策 |
| --- | --- |
| ADR-001 | 采用微服务而非模块化单体 |
| ADR-002 | Kafka + Outbox 保证跨服务最终一致性 |
| ADR-003 | 模型只生成候选决策 |
| ADR-004 | 实盘订单以幂等状态机和对账闭环 |
| ADR-005 | Python 回测使用隔离 Kubernetes Job |
| ADR-006 | 一期 Ollama/vLLM 仅配置，不调用 |
| ADR-007 | 币安按产品域拆分帐号 Scope，共享统一订单状态机 |
| ADR-008 | 币安生产密钥优先 Ed25519，KMS 托管且禁止提现权限 |

正式实施前应将每项 ADR 独立成文，记录背景、备选方案和后果。

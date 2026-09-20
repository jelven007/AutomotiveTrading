# 量化交易 SaaS 文档中心

2026-09-20 确认：A 股数据范围仅为上交所（SSE）和深交所（SZSE）。
行情文档中的“全市场”均指沪深，北交所不属于数据接入、补齐或验收范围。
范围基线见 [专项需求 0.2](requirements/a-share-market-data-requirements.md)，
现有代码的对齐事项见 [Sidecar 说明](../services/mootdx-collector/README.md#范围对齐状态)。

2026-09-20 确认：币安改用 NautilusTrader，当前范围为现货和 U 本位永续；
U 本位包含杠杆及全仓/逐仓保证金模式。币安不使用官方 SDK、云 KMS、独立
Risk Service 或自研协议栈，详情见
[专项设计](plans/2026-09-20-binance-nautilustrader-integration-design.md)。

## 文档清单

| 编号 | 文档 | 用途 |
| --- | --- | --- |
| QT-SPEC-001 | [产品与技术总规格](plans/2026-09-18-quant-trading-saas-spec.md) | 已确认范围与总体基线 |
| QT-SRS-001 | [需求规格说明书](requirements/software-requirements-specification.md) | 可验证功能与非功能需求 |
| QT-RTM-001 | [需求追踪矩阵](requirements/requirements-traceability-matrix.md) | 需求、设计和测试映射 |
| QT-TDS-001 | [技术方案](architecture/technical-solution.md) | 架构、服务、数据流与技术选型 |
| QT-API-001 | [API 与事件规格](architecture/api-event-specification.md) | REST、WebSocket 和 Kafka 契约 |
| QT-DM-001 | [数据模型](architecture/data-model.md) | 核心实体、约束与保留策略 |
| QT-TS-001 | [测试规格说明书](testing/test-specification.md) | 测试范围、方法和退出标准 |
| QT-TC-001 | [核心测试用例](testing/test-cases.md) | P0/P1 核心用例 |
| QT-UAT-001 | [验收与发布准入](testing/acceptance-plan.md) | 业务验收与上线关卡 |
| QT-SEC-001 | [安全与威胁模型](security/security-and-threat-model.md) | 威胁、控制和安全验收 |
| QT-OPS-001 | [部署与运维方案](operations/deployment-and-operations.md) | 火山引擎部署、监控和 Runbook |
| QT-INT-001 | [交易通道接入计划](integrations/broker-integration-plan.md) | 同花顺、财信、富途、长桥、币安接入 |
| QT-REQ-BIN-NT-001 | [币安 NautilusTrader 接入需求](requirements/binance-nautilustrader-requirements.md) | 当前币安范围、约束和验收标准 |
| QT-DES-BIN-NT-001 | [币安 NautilusTrader 接入设计](plans/2026-09-20-binance-nautilustrader-integration-design.md) | 当前架构、模块、接口、数据、依赖和风险 |
| QT-PLAN-BIN-NT-001 | [币安 NautilusTrader 实施计划](plans/2026-09-20-binance-nautilustrader-integration-implementation-plan.md) | TDD 迁移步骤、文件和提交顺序 |
| QT-TP-BIN-NT-001 | [币安 NautilusTrader 测试计划](testing/binance-nautilustrader-test-plan.md) | 单元、组件、Testnet、故障和生产灰度 |
| QT-OPS-BIN-NT-001 | [币安 NautilusTrader 运维手册](operations/binance-nautilustrader-runbook.md) | 部署、帐号操作、排障、恢复和升级 |
| QT-INT-BIN-001 | [币安生产准入状态](integrations/binance-production-readiness.md) | 当前实现差距和真实资金闸门 |
| QT-DES-TRD-001 | [旧交易帐号与币安接入设计](plans/2026-09-19-trading-account-and-binance-integration-design.md) | Superseded，仅保留历史 |
| QT-SRS-CNMD-001 | [A 股行情与分析系统需求](requirements/a-share-market-data-requirements.md) | 沪深范围、MOOTDX 数据持久化与前端需求 |
| QT-DES-CNMD-001 | [A 股行情与前端分析设计](plans/2026-09-20-a-share-market-data-design.md) | 沪深采集、存储、质量、API 和页面设计 |
| QT-TP-CNMD-001 | [A 股行情测试计划](testing/a-share-market-data-test-plan.md) | 沪深数据完整性、范围过滤、性能、恢复和前端验收 |
| QT-PLAN-001 | [详细实施计划](plans/2026-09-18-quant-trading-saas-implementation-plan.md) | 任务、文件、测试和提交顺序 |
| QT-PLAN-TRD-001 | [旧币安交易实施计划](plans/2026-09-19-binance-production-trading-implementation-plan.md) | Superseded，仅保留历史 |
| QT-PLAN-CNMD-001 | [A 股行情实施计划](plans/2026-09-20-a-share-market-data-implementation-plan.md) | 基础设施、数据流水线、前端与验收步骤 |
| — | [mootdx Sidecar 实施计划](plans/2026-09-20-mootdx-sidecar.md) | 隔离采集、持久队列、沪深覆盖与范围对齐 |
| — | [mootdx Sidecar 验收记录](testing/results/mootdx-sidecar-acceptance.md) | 真实沪深采集、重放去重与历史证据 |

## 文档优先级

发生冲突时按以下优先级处理：

1. 经签署的需求变更记录。
2. 已确认的专项需求与专项设计。
3. 需求规格说明书。
4. 技术方案与接口/数据规格。
5. 测试规格与测试用例。
6. 产品与技术总规格。

## 状态约定

- Draft：编写中。
- Review：待评审。
- Approved：已审批，可作为实现基线。
- Superseded：已被新版本替代。

## 维护规则

- 所有正式需求使用稳定编号。
- 需求变更同步更新追踪矩阵和测试用例。
- 外部集成结论必须附官方或合同证据。
- 禁止将密钥、账号和生产数据写入文档。
- 每次发布记录适用的文档版本和 Git Commit。

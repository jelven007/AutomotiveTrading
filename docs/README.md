# 量化交易 SaaS 文档中心

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
| QT-INT-001 | [交易通道接入计划](integrations/broker-integration-plan.md) | 富途、同花顺、财信接入 |

## 文档优先级

发生冲突时按以下优先级处理：

1. 经签署的需求变更记录。
2. 需求规格说明书。
3. 技术方案与接口/数据规格。
4. 测试规格与测试用例。
5. 产品与技术总规格。

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

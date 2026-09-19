# 需求追踪矩阵

> 文档编号：QT-RTM-001
>
> 版本：1.1-draft

## 1. 追踪规则

- 需求来源：`software-requirements-specification.md`
- 设计来源：`../architecture/technical-solution.md`
- 接口来源：`../architecture/api-event-specification.md`
- 数据来源：`../architecture/data-model.md`
- 测试来源：`../testing/test-cases.md`
- 状态：Planned、Implemented、Verified、Blocked

## 2. 功能追踪

| 需求范围 | 设计组件 | 主要测试集 | 状态 |
| --- | --- | --- | --- |
| FR-IAM-* | Identity & Tenant、Gateway | TC-IAM-* | Planned |
| FR-HOME-* | Web BFF、Home Workspace | TC-HOME-* | Planned |
| FR-NEWS-* | News Service | TC-NEWS-* | Planned |
| FR-DATA-* | Instrument、Market Data | TC-DATA-* | Planned |
| FR-STR-* | Strategy、Trigger | TC-STR-* | Planned |
| FR-MDL-* | Model Configuration、KMS | TC-MDL-* | Planned |
| FR-AI-* | Model Gateway、Portfolio Coordinator | TC-AI-* | Planned |
| FR-BT-* | Backtest Scheduler、Runner | TC-BT-* | Planned |
| FR-TRD-001~012 | Trading、Broker Connectors | TC-TRD-000~007 | Planned |
| FR-TRD-013~014 | Trading Web、Account Binding | TC-TRD-008 | Planned |
| FR-TRD-015~020 | Binance Connector、KMS、Trading | TC-TRD-009~014 | Planned |
| FR-RSK-001~004 | Risk Service | TC-RSK-001~003 | Planned |
| FR-RSK-005~007 | Binance Risk Guard | TC-RSK-004 | Planned |
| FR-REC-* | Reconciliation Service | TC-REC-* | Planned |
| FR-SAA-* | Subscription & Billing | TC-SAA-* | Planned |

## 3. 非功能追踪

| 需求 | 验证方式 | 测试编号 | 状态 |
| --- | --- | --- | --- |
| NFR-SEC-001 | KMS 集成与密钥不可回显 | TC-SEC-001 | Planned |
| NFR-SEC-002 | 日志扫描 | TC-SEC-002 | Planned |
| NFR-SEC-003 | 审计完整性验证 | TC-SEC-003 | Planned |
| NFR-SEC-004 | 提示词注入测试 | TC-SEC-004 | Planned |
| NFR-SEC-005 | 越权与恶意代码测试 | TC-SEC-005 | Planned |
| NFR-REL-001 | 月度 SLI 计算 | TC-REL-001 | Planned |
| NFR-REL-002 | 交易链路 SLI | TC-REL-002 | Planned |
| NFR-REL-003 | 消息故障注入 | TC-REL-003 | Planned |
| NFR-REL-004 | 数据恢复演练 | TC-REL-004 | Planned |
| NFR-REL-005 | 灾备切换演练 | TC-REL-005 | Planned |
| NFR-PERF-001 | 查询压测 | TC-PERF-001 | Planned |
| NFR-PERF-002 | 风控链路压测 | TC-PERF-002 | Planned |
| NFR-PERF-003 | 事件触发压测 | TC-PERF-003 | Planned |
| NFR-PERF-004 | WebSocket 容量测试 | TC-PERF-004 | Planned |
| NFR-OBS-* | 指标、日志、告警演练 | TC-OBS-* | Planned |
| NFR-MNT-* | 架构与契约审查 | TC-ARC-* | Planned |

## 4. 外部依赖追踪

| 依赖 | 负责人 | 验收证据 | 状态 |
| --- | --- | --- | --- |
| 富途 OpenD 授权与测试账号 | 待指定 | 协议、账号、联调报告 | Blocked |
| 同花顺模拟盘开放能力 | 待指定 | 接口文档、账号、联调报告 | Blocked |
| 财信证券正式量化通道 | 待指定 | 券商确认、账号、联调报告 | Blocked |
| 长桥 OpenAPI 权限与测试账号 | 待指定 | 协议、账号、联调报告 | Blocked |
| 币安生产现货帐号与 API 权限 | 待指定 | 权限截图、只读联调、审计记录 | Blocked |
| 币安全仓/逐仓杠杆资格 | 待指定 | 产品开通、借还款与风险测试报告 | Blocked |
| 币安 U 本位永续资格 | 待指定 | 产品开通、小额灰度与对账报告 | Blocked |
| 币安固定出口 IP 白名单 | 待指定 | 网络变更单、Key 权限检查 | Blocked |
| 三地行情与资讯授权 | 待指定 | 采购合同、授权范围 | Blocked |
| 法律与合规评审 | 待指定 | 书面评审结论 | Blocked |

## 5. 变更控制

新增或修改需求时必须：

1. 分配新需求编号，不复用已删除编号。
2. 更新设计映射。
3. 更新至少一个测试用例。
4. 评估数据迁移、安全、合规和外部接口影响。
5. 通过规格评审后进入实现。

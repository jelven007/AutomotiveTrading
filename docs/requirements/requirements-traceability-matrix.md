# 需求追踪矩阵

> 文档编号：QT-RTM-001
>
> 版本：1.3-draft

## 1. 追踪规则

- 需求来源：`software-requirements-specification.md`；币安专项使用
  `binance-nautilustrader-requirements.md`
- 设计来源：`../architecture/technical-solution.md`；币安专项使用
  `../plans/2026-09-21-binance-single-account-phased-design.md`
- 接口来源：`../architecture/api-event-specification.md`
- 数据来源：`../architecture/data-model.md`
- 测试来源：`../testing/test-cases.md`；币安专项使用
  `../testing/binance-nautilustrader-test-plan.md`
- 状态：Planned、Partial、Implemented、Verified、Blocked

## 2. 功能追踪

| 需求范围 | 设计组件 | 主要测试集 | 状态 |
| --- | --- | --- | --- |
| FR-IAM-* | Identity & Tenant、Gateway | TC-IAM-* | Planned |
| FR-HOME-* | Web BFF、Home Workspace | TC-HOME-* | Planned |
| FR-NEWS-* | News Service | TC-NEWS-* | Planned |
| FR-DATA-* | Instrument、Market Data | TC-DATA-* | Planned |
| FR-CNMD-001~022 | 沪深数据链路与存储 | TC-CNMD-001~014、TC-CNMD-REL-* | Planned |
| FR-CNMD-023~028 | Web Data Workspace | TC-CNMD-WEB-* | Planned |
| FR-CNMD-* 沪深范围约束 | SSE/SZSE 过滤与覆盖聚合 | TC-CNMD-014 | Planned |
| FR-STR-* | Strategy、Trigger | TC-STR-* | Planned |
| FR-MDL-* | Model Configuration、KMS | TC-MDL-* | Planned |
| FR-AI-* | Model Gateway、Portfolio Coordinator | TC-AI-* | Planned |
| FR-BT-* | Backtest Scheduler、Runner | TC-BT-* | Planned |
| FR-TRD-001~012 | Trading、Broker Connectors | TC-TRD-000~007 | Planned |
| FR-TRD-013~014 | Trading Web、Account Binding | TC-TRD-008~009 | Verified |
| FR-BIN-NT-001~011 | 单帐号、凭据和权限 | TC-BIN-NT-001~005、030~033 | Partial |
| FR-BIN-NT-012~019 | 只读聚合与降级 | TC-BIN-NT-006~007、020~022、034~036 | Planned |
| FR-BIN-NT-020~030 | 人工交易、MFA、幂等与 U 本位设置 | TC-BIN-NT-040~052 | Planned |
| FR-RSK-001~004 | Risk Service | TC-RSK-001~003 | Partial |
| FR-RSK-005~007 | 本地风控、USD-M | TC-TRD-011、TC-RSK-004 | Planned |
| FR-REC-* | Reconciliation Service | TC-REC-* | Planned |
| FR-SAA-* | Subscription & Billing | TC-SAA-* | Planned |

## 3. 非功能追踪

| 需求 | 验证方式 | 测试编号 | 状态 |
| --- | --- | --- | --- |
| NFR-SEC-001 | KMS 及币安本地主密钥加密与不可回显 | TC-SEC-001、TC-BIN-NT-001~003 | Planned |
| NFR-SEC-002 | 日志扫描 | TC-SEC-002 | Partial |
| NFR-SEC-003 | 审计完整性验证 | TC-SEC-003 | Partial |
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
| NFR-CNMD-001~003 | 全市场采集与查询压测 | QT-TP-CNMD-001 第 6 节 | Planned |
| NFR-CNMD-004~007 | 重放、幂等与缓存恢复 | TC-CNMD-REL-* | Planned |
| NFR-CNMD-008~010 | 前端性能、可访问性与敏感信息检查 | TC-CNMD-WEB-* | Planned |
| NFR-BIN-NT-001~008 | 锁版、快照、隔离、恢复与脱敏 | QT-TP-BIN-NT-001 第 3~12 节 | Planned |
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
| 币安 U 本位永续资格 | 待指定 | 产品开通、小额灰度与对账报告 | Blocked |
| 币安固定出口 IP 白名单 | 待指定 | 网络变更单、Key 权限检查 | Blocked |
| NautilusTrader 1.231.0 | 待指定 | wheel、Testnet 契约、SBOM | Blocked |
| 三地行情与资讯授权 | 待指定 | 采购合同、授权范围 | Blocked |
| 法律与合规评审 | 待指定 | 书面评审结论 | Blocked |

## 5. 变更控制

2026-09-20 用户确认 A 股数据仅覆盖上交所（SSE）和深交所（SZSE）。
需求、设计及测试文档已同步；北交所不再作为采集、补齐或验收待办，
不计入应采、覆盖率和缺口。上述范围约束行的 Planned 指代码与新增用例尚待对齐，
不代表已验证；既有沪深实采证据见
[Sidecar 验收记录](../testing/results/mootdx-sidecar-acceptance.md)，
实现差异见 [范围对齐状态](../../services/mootdx-collector/README.md#范围对齐状态)。

2026-09-21 用户确认币安采用单帐号分阶段方案：阶段一只查询权限、现货余额、
U 本位余额和持仓；阶段二增加人工下单、单笔撤单、杠杆和保证金模式。重新绑定
覆盖旧帐号，绑定不要求 MFA，交易写入要求短时 MFA 会话和幂等键。新需求、设计
和测试分别见 `QT-REQ-BIN-NT-001` 2.0、`QT-DES-BIN-SIMPLE-001` 和
`QT-TP-BIN-NT-001` 2.0；旧多帐号方案不再作为实现或验收依据。

新增或修改需求时必须：

1. 分配新需求编号，不复用已删除编号。
2. 更新设计映射。
3. 更新至少一个测试用例。
4. 评估数据迁移、安全、合规和外部接口影响。
5. 通过规格评审后进入实现。

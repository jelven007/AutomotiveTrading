# 文档

当前系统只包含 Web、Identity、Trading、MySQL 和 Binance。产品界面统一以
“B”指代 Binance，代码、接口路径和运维内容继续使用 `Binance`。

## 当前基线

- [技术方案总览](architecture/2026-09-21-technical-overview.md)
- [Web 前端三页全流程设计](frontend/2026-09-21-web-three-page-design.md)
- [生产准入状态](integrations/binance-production-readiness.md)
- [部署与排障](operations/binance-nautilustrader-runbook.md)

## 演进记录

- [单账号分阶段设计](plans/2026-09-21-binance-single-account-phased-design.md)
- [分阶段实施计划](plans/2026-09-21-binance-single-account-phased-implementation-plan.md)
- [最小系统清理计划](plans/2026-09-21-minimal-binance-system-cleanup.md)

发生冲突时，以单账号分阶段设计和实施计划为准。文档、日志与测试数据均不得包含
API Key、Secret、JWT、主密钥或数据库密码。

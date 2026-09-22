# Quant Desk

面向单用户的 B Demo 账户查询与人工模拟交易系统。产品界面统一使用简称“B”，
代码、接口和运维文档保留 `Binance` 技术标识。

## 组成

- `apps/web`：首页（公开行情与资讯）、策略列表、交易（行情、资产与订单）、
  登录与用户信息；桌面端和移动端使用统一的交易工作台视觉。
- `services/identity-tenant`：邮箱密码认证、JWT、刷新令牌和 TOTP MFA。
- `services/trading`：单 Binance 账号、AES-256-GCM 凭据存储及 NautilusTrader。
- `infra/compose`：MySQL 与上述三个应用服务的单机部署。

当前提供 Demo 账号、现货余额、U 本位余额和持仓查询。人工下单、撤单、杠杆和
保证金模式下一阶段只接入 Demo；主网实盘后置。当前前端采用列表/表格优先的
高密度布局，行情卡、资产摘要以及策略/订单工具栏具有统一尺寸和响应式规则。
生产环境仅允许首位所有者完成注册，全系统共享一个 B 账号槽位；Trading 启动时
从加密凭据恢复 Runtime，账号绑定、替换和删除均要求 5 分钟内完成 MFA。
前端页面结构见
[Web 前端三页全流程设计](docs/frontend/2026-09-21-web-three-page-design.md)。

## 本地验证

```bash
uv sync --all-packages
pnpm install
make lint
make test
make build
```

## 部署

```bash
bash scripts/deploy.sh init
bash scripts/deploy.sh up
bash scripts/deploy.sh status
```

部署前必须准备 32 字节主密钥、固定出口 IP、B Demo Key 和可信 HTTPS 入口。
当前代码不能通过配置切换主网。具体要求见
[B Demo 运维手册](docs/operations/binance-nautilustrader-runbook.md)。

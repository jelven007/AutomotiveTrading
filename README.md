# Quant Desk

面向单用户的币安账户与人工交易系统。

## 组成

- `apps/web`：首页（币安公开行情与资讯）、策略看板、交易（总资产与当前订单）、
  登录与用户信息。
- `services/identity-tenant`：邮箱密码认证、JWT、刷新令牌和 TOTP MFA。
- `services/trading`：单币安账号、AES-256-GCM 凭据存储及 NautilusTrader。
- `infra/compose`：MySQL 与上述三个应用服务的单机部署。

阶段一只提供权限、现货余额、U 本位余额和持仓查询。人工下单、撤单、杠杆和
保证金模式按阶段二计划实施，生产写入默认关闭。前端页面结构见
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

部署前必须准备 32 字节主密钥、固定出口 IP 和可信 HTTPS 入口。具体要求见
[Binance 运维手册](docs/operations/binance-nautilustrader-runbook.md)。

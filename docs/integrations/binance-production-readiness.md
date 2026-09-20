# 币安生产交易实现与准入状态

> 文档编号：QT-INT-BIN-001
>
> 日期：2026-09-20
>
> 状态：方案已重设，等待 NautilusTrader 迁移

## 1. 当前决策

2026-09-20 起，币安集成以
[`QT-DES-BIN-NT-001`](../plans/2026-09-20-binance-nautilustrader-integration-design.md)
为唯一当前设计：

- 使用 NautilusTrader，不使用币安官方 SDK。
- 支持现货和 U 本位永续。
- 支持 U 本位杠杆、全仓/逐仓保证金和单向/双向持仓。
- 不支持现货杠杆、借还款、币本位和期权。
- 用户登录后从“交易 → 币安”添加帐号。
- 可保存多个帐号，但同一时间只运行一个活动帐号。
- 凭据由 ECS 本地主密钥使用 AES-256-GCM 加密入库，不使用 KMS。
- Trading Service 内置最小风控，不依赖独立 Risk Service。

## 2. 已有可复用能力

- Web 登录、会话刷新和 TOTP MFA。
- 交易菜单及币安帐号添加入口。
- 帐号、订单、急停和审计的基础表结构。
- FastAPI 身份鉴权、RFC 7807 错误和 Trace ID。
- MySQL 部署、迁移和 Web 反向代理基础。
- 写请求幂等和未知订单禁止盲目重试原则。
- NautilusTrader 1.231.0 已锁定，Spot/USD-M 配置 POC 和目标 Linux x86_64
  wheel 检查已通过。

这些能力需要按新 API 和数据模型改造后才能计入新方案验收。

## 3. 待替换能力

以下现有代码属于旧方案，迁移前不得视为 Nautilus 生产能力：

```text
services/trading/src/trading/binance/client.py
services/trading/src/trading/binance/signing.py
services/trading/src/trading/risk.py
services/trading/src/trading/secrets.py 中的 KMS 路径
services/trading/tests/test_binance_client.py
services/trading/tests/test_binance_signing.py
infra/compose/docker-compose.deploy.yml 中的 binance-readonly Profile
```

现有代码实现了自研签名、直接 REST、Margin Scope、KMS 和远程 Risk 调用，与新
方案冲突。删除前必须先完成 Nautilus Testnet 等价验证。

## 4. 当前阻塞

- ECS 到 Binance Spot/USD-M 的 DNS 与 TLS 路径尚未恢复。
- 本地主密钥文件、AES-GCM 数据模型和轮换流程尚未实现。
- 多帐号单活动状态机尚未实现。
- Web 仍展示全仓/逐仓现货杠杆和 RSA。
- Testnet 与生产真实帐号尚未验证。
- 公网入口仍需完成可信证书签发。

## 5. 生产配置目标

```text
ENVIRONMENT=production
AUTH_JWT_SECRET=<managed secret>
BINANCE_CREDENTIAL_MASTER_KEY_FILE=/run/secrets/binance_credential_master_key
FIXED_EGRESS_IP_CONFIGURED=true
PUBLIC_BASE_URL=https://<trusted-host>
BINANCE_TESTNET=false
BINANCE_LIVE_TRADING_ENABLED=false
BINANCE_MAX_ORDER_NOTIONAL=<decimal>
BINANCE_MAX_POSITION_NOTIONAL=<decimal>
BINANCE_MAX_FUTURES_LEVERAGE=<integer>
BINANCE_MAX_DAILY_LOSS=<decimal>
```

主密钥文件不得存入 `.env`。

## 6. 准入顺序

1. Nautilus 依赖和 Fake Node POC。
2. 登录后帐号添加、本地加密和单活动帐号。
3. Spot/USD-M 只读 Testnet。
4. Testnet 现货交易闭环。
5. Testnet U 本位低杠杆逐仓闭环。
6. 断线、超时、重启和帐号切换故障演练。
7. 生产只读观察。
8. 最小金额现货灰度。
9. 低杠杆 U 本位逐仓灰度。
10. 自动策略另行设计和审批。

任何未决订单、重复订单、账实不符或凭据泄漏问题未关闭前，不得进入下一阶段。

## 7. 验收证据

专项测试以
[`QT-TP-BIN-NT-001`](../testing/binance-nautilustrader-test-plan.md)
为准，实施顺序以
[`QT-PLAN-BIN-NT-001`](../plans/2026-09-20-binance-nautilustrader-integration-implementation-plan.md)
为准，排障流程见
[`QT-OPS-BIN-NT-001`](../operations/binance-nautilustrader-runbook.md)。
M0 验收证据见
[`QT-RESULT-BIN-NT-M0-001`](../testing/results/binance-nautilustrader-m0-poc.md)。

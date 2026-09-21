# 币安生产接入与准入状态

> 文档编号：QT-INT-BIN-001
>
> 日期：2026-09-21
>
> 状态：单账号分阶段方案已确认，等待实现对齐

## 1. 当前决策

币安集成以
[`QT-DES-BIN-SIMPLE-001`](../plans/2026-09-21-binance-single-account-phased-design.md)
为唯一当前设计：

- 每个用户只绑定一个 HMAC 币安账号。
- 重新绑定成功时覆盖旧账号，失败时保留旧账号。
- 阶段一只查询权限、现货余额、U 本位余额和持仓。
- 阶段二增加人工市价/限价下单、单笔撤单、杠杆和保证金模式。
- 保留一个 NautilusTrader Runtime，不建设后台账户同步。
- 凭据由 ECS 本地主密钥使用 AES-256-GCM 加密入库。
- 绑定不要求 MFA；阶段二交易写入要求短时 MFA 会话。
- 自动策略交易不属于当前方案。

## 2. 已有可复用能力

- Web 邮箱登录、会话刷新和 TOTP MFA。
- 精简的币安账号录入弹窗。
- FastAPI 身份鉴权、RFC 7807 错误和 Trace ID。
- MySQL、Alembic、Web 反向代理和 ECS 部署。
- AES-256-GCM 本地主密钥及只读挂载。
- 固定出口 IP 配置开关。
- NautilusTrader 1.231.0 Spot/USD-M 配置 POC。
- 写请求幂等和不确定结果不盲目重试的基础代码。

这些能力需要按单账号 API 和数据模型改造后才能计入新方案验收。

## 3. 当前实现差距

- 当前 Trading API 仍使用通用多账号 `/accounts` 路径。
- 当前模型仍包含 Scope、`is_active`、激活/停用和多账号状态。
- 当前权限探测客户端还包含订单、借还款和杠杆等写方法。
- 当前 Web 仍展示账号列表、当前账号、激活/停用和急停。
- Nautilus Runtime Manager 和聚合账户查询尚未完成。
- Spot/USD-M 余额和持仓尚未通过新 `/overview` 契约返回。
- 阶段二订单执行尚未切换到 Nautilus。

## 4. 外部阻塞

- ECS 到 Binance Spot/USD-M 交易域名仍存在 TLS 重置或连接超时。
- 生产只读账号尚未完成真实三类数据核对。
- Testnet 订单、撤单、杠杆和保证金模式尚未验收。
- API 网关到 ECS 的访问仍需云防火墙放行规则完成验证。

上述任一网络阻塞存在时，不得把接口失败解释为凭据错误。

## 5. 生产配置目标

```text
ENVIRONMENT=production
AUTH_JWT_SECRET=<managed secret>
BINANCE_CREDENTIAL_MASTER_KEY_FILE=/opt/quant-trading/secrets/credential-master-key
FIXED_EGRESS_IP_CONFIGURED=true
PUBLIC_BASE_URL=https://<trusted-host>
BINANCE_TESTNET_ENABLED=false
LIVE_TRADING_ENABLED=false
```

主密钥不得进入 `.env`，宿主机权限必须为 `600`。

阶段二只新增：

```text
LIVE_TRADING_ENABLED=true
BINANCE_TRADING_SESSION_TTL_SECONDS=900
```

## 6. 准入顺序

### 阶段一

1. 单账号 API 和数据库约束。
2. 权限探测客户端收敛为只读。
3. 候选 Runtime 验证和原子替换。
4. Spot/USD-M 聚合账户查询。
5. 单账号 Web 页面。
6. 真实生产只读账号核对。

### 阶段二

1. MFA 交易会话和统一写入门禁。
2. Spot Testnet 市价、限价和单笔撤单。
3. USD-M Testnet 市价、限价和单笔撤单。
4. USD-M 杠杆和 `cross|isolated` 保证金模式。
5. 超时、断线、重启和幂等故障演练。
6. 生产限价撤单验证。
7. 生产最小金额现货灰度。
8. 生产低杠杆 U 本位灰度。

自动策略不进入本准入序列。

## 7. 硬门禁

- API Key 必须启用读取和固定 IP 限制。
- API Key 必须关闭提现、内部划转和通用划转。
- 阶段二才允许开启现货或 U 本位交易权限。
- `LIVE_TRADING_ENABLED=false` 时不得注册可执行交易的业务能力。
- 所有交易写接口必须要求 MFA 交易会话和 `Idempotency-Key`。
- `pending_reconciliation` 未收敛前不得重复提交同一业务请求。
- 凭据泄漏、重复订单或旧账号错误覆盖属于立即停止发布条件。

## 8. 验收证据

专项测试以
[`QT-TP-BIN-NT-001`](../testing/binance-nautilustrader-test-plan.md)
2.0 为准，实施顺序以
[`QT-PLAN-BIN-SIMPLE-001`](../plans/2026-09-21-binance-single-account-phased-implementation-plan.md)
为准，运维流程见
[`QT-OPS-BIN-NT-001`](../operations/binance-nautilustrader-runbook.md)。

已完成的 Nautilus M0 证据仍可复用：
[`QT-RESULT-BIN-NT-M0-001`](../testing/results/binance-nautilustrader-m0-poc.md)。

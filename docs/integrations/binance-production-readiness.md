# Binance 生产准入

> 日期：2026-09-21
>
> 状态：阶段一已部署，真实账户验收阻塞

## 当前范围

- 每个用户只保存一个 HMAC 币安账号。
- 重新绑定成功后覆盖旧账号，失败时保留旧状态。
- 阶段一只查询权限、Spot 余额、USD-M 余额和非零持仓。
- 阶段二只增加人工市价/限价单、单笔撤单、杠杆和保证金模式。
- 凭据使用 ECS 本地主密钥和 AES-256-GCM 加密。
- 绑定不要求 MFA；阶段二写入要求短时 MFA 会话和幂等键。

## 已完成

- 单账号 API、数据库唯一约束和原子替换。
- 只读权限探测器。
- NautilusTrader 1.231.0 双客户端 Runtime。
- 聚合账户查询、局部降级和 5 秒快照。
- 首页币安公开行情/资讯、策略看板与交易页（总资产 + 当前订单占位）。
- 最小 Docker Compose 部署。
- 生产写入默认关闭。

## 外部阻塞

- ECS 无法完成 `api.binance.com`、`api1` 至 `api4` 和
  `fapi.binance.com` 的 HTTPS 请求。
- 公网入口证书链尚不受客户端信任。
- 尚未使用专用生产只读 Key 对照 Binance 控制台数据。

上述问题解决前，不进入阶段二。

## 生产配置

```text
ENVIRONMENT=production
BINANCE_CREDENTIAL_MASTER_KEY_FILE=/opt/quant-trading/secrets/credential-master-key
BINANCE_CREDENTIAL_MASTER_KEY_UID=100
FIXED_EGRESS_IP_CONFIGURED=true
BINANCE_TESTNET_ENABLED=false
LIVE_TRADING_ENABLED=false
PUBLIC_BASE_URL=https://<trusted-host>
```

主密钥必须是 32 个原始随机字节、权限 `600`，并只读挂载。

## 准入顺序

1. 修复 Binance 签名接口出口。
2. 配置可信 HTTPS 域名。
3. 录入专用只读 Key。
4. 核对权限、Spot、USD-M 余额和持仓。
5. 完成阶段二 Testnet 下单、撤单与故障演练。
6. 人工批准后才允许设置 `LIVE_TRADING_ENABLED=true`。

任何凭据泄漏、重复订单或不确定订单无法收敛，都必须立即停止发布。

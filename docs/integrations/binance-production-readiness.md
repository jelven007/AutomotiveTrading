# B Demo 接入与主网准入

> 日期：2026-09-22
>
> 状态：Demo-only 基线完成，模拟账号验收待执行

## 当前范围

- 生产部署仅允许首位所有者注册，全系统只保存一个 HMAC B 模拟账号。
- 重新绑定成功后覆盖旧账号，失败时保留旧状态。
- 当前只查询 Demo 账号、Spot 余额、USD-M 余额和非零持仓。
- 下一阶段只增加 Demo 人工市价/限价单、单笔撤单、杠杆和保证金模式。
- 凭据使用 ECS 本地主密钥和 AES-256-GCM 加密。
- 账号绑定和替换不要求 MFA；删除要求 5 分钟内的 MFA，模拟交易写入还要求幂等键。
- 当前 Runtime 固定为 `BinanceEnvironment.DEMO`，没有主网配置分支。

## 已完成

- 单所有者注册门禁、全局单账号数据库约束和原子替换。
- Trading 启动时从加密凭据恢复 Runtime，关闭时停止 Runtime。
- Spot Demo 签名账号探测器。
- NautilusTrader 1.231.0 双客户端 Runtime。
- 聚合账户查询、局部降级和 5 秒快照。
- 首页公开行情卡与资讯列表、策略表格，以及交易页的资产和订单表格。
- 用户界面统一使用“B”简称；技术标识符和 API 契约保持 `Binance`。
- 桌面端与移动端共用统一设计令牌和响应式布局。
- 最小 Docker Compose 部署。
- Demo 写入默认关闭，主网连接不可配置。

## 待验收

- ECS 需要验证 Spot Demo 与 USD-M Demo 的 REST/WebSocket 出口。
- 公网入口证书链尚不受客户端信任。
- 尚未使用专用 Demo Key 对照 B 模拟账户数据。

上述问题解决前，不实现 Demo 下单。

## 生产配置

```text
ENVIRONMENT=production
SINGLE_OWNER_MODE=true
BINANCE_CREDENTIAL_MASTER_KEY_FILE=/opt/quant-trading/secrets/credential-master-key
BINANCE_CREDENTIAL_MASTER_KEY_UID=100
BINANCE_ENVIRONMENT=demo
DEMO_TRADING_ENABLED=false
PUBLIC_BASE_URL=https://<trusted-host>
```

主密钥必须是 32 个原始随机字节、权限 `600`，并只读挂载。

## 准入顺序

1. 打通 Spot/USD-M Demo 签名接口与 WebSocket 出口。
2. 配置可信 HTTPS 域名。
3. 录入专用 Demo Key。
4. 核对 Spot、USD-M 余额和持仓。
5. 实现并启用 `DEMO_TRADING_ENABLED=true`，完成下单、撤单与故障演练。
6. Demo 全链路稳定后，另行评审主网只读接入与实盘灰度。

任何凭据泄漏、重复订单或不确定订单无法收敛，都必须立即停止发布。不得通过增加
主网 URL 或恢复旧 `LIVE_TRADING_ENABLED` 变量绕过当前隔离。

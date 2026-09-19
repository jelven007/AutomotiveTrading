# 币安生产交易实现与准入状态

> 文档编号：QT-INT-BIN-001
>
> 日期：2026-09-19
>
> 状态：代码基础已实现，真实资金验收阻塞

## 1. 已实现

- 交易页面固定提供沪深、港美、币安三个入口和通道白名单。
- 币安帐号绑定支持 Ed25519、HMAC、RSA，凭据字段提交后立即清理。
- `trading` 服务按租户保存帐号、Scope、订单、操作、急停和 Outbox。
- 币安请求使用服务器时间偏移，`recvWindow` 不超过 5000 ms。
- 帐号绑定检查读取、现货、杠杆、U 本位和提现权限；提现权限会拒绝或停用。
- 支持现货、全仓杠杆、逐仓杠杆、U 本位订单提交、查询和撤单连接器。
- 下单前检查交易对状态、数量/价格步长和限价单最小名义金额。
- 支持资金快照、杠杆借还款和 U 本位杠杆设置。
- 生产写操作要求租户角色、近期 MFA、独立幂等键、风险审批和未触发急停。
- 写请求超时保存为 `unknown`，相同幂等键只返回原记录，不重放订单。
- Risk Service 已实现版本化租户策略、Decimal 风险计算和 60 秒单次审批令牌。
- KMS Adapter 已实现火山 KMS 信封加密、租户上下文绑定和不可恢复删除。
- Trading 调用 Risk/KMS 时使用独立服务令牌，KMS 解析和删除显式携带租户。
- FastAPI 校验错误不会返回 API Key、Secret 或私钥输入。

## 2. 自动化证据

```text
services/trading/tests/test_accounts.py
services/trading/tests/test_binance_signing.py
services/trading/tests/test_binance_client.py
services/trading/tests/test_orders.py
services/trading/tests/test_account_operations.py
services/trading/tests/test_api.py
services/trading/tests/test_security.py
services/trading/tests/test_internal_service_clients.py
services/risk/tests/
services/kms-adapter/tests/
apps/web/src/features/trading/AccountBindingDialog.test.tsx
apps/web/src/features/trading/TradingWorkspace.test.tsx
apps/web/src/app/AppShell.test.tsx
```

浏览器已在 1280x720 和 390x664 视口验证：

- Appbar 单行显示，主导航在窄屏横向滚动。
- 三个交易路由和四个币安产品标签正常。
- 帐号绑定弹窗无横向溢出，移动端内部滚动正常。
- 币安产品标签切换会更新对应工作区。

## 3. 未完成项

以下能力未完成前，不得宣称币安生产交易已验收：

- Spot、Margin 和 USD-M User Data Stream 的续期、断线恢复和事件去重。
- 开放委托、成交、手续费、利息、资金费率和 ADL 的完整同步。
- 全仓/逐仓资金划转和最大可借库存预检查。
- U 本位持仓模式、保证金模式变更和交易所杠杆分层上限同步。
- 订单、成交、资产、负债、持仓和费用的 Reconciliation Service。
- Outbox 到 Redpanda 的发布器、重试、死信和监控。
- Risk Service 的频率、集中度、亏损、借款上限、利息、保证金/持仓模式和资金费率
  等完整规则，以及借款、调杠杆、撤单和还款动作的独立审批契约。
- 火山引擎 KMS 适配器的真实联调和密钥轮换演练。
- 固定出口 EIP、币安 Key IP 白名单和生产网络域名白名单。
- 生产帐号、产品资格、司法辖区、服务条款和法务合规书面确认。

## 4. 生产闸门

服务在生产环境启动时要求：

```text
ENVIRONMENT=production
AUTH_JWT_SECRET=<managed secret>
SECRET_BACKEND=kms
KMS_URL=https://...
KMS_SERVICE_TOKEN=<独立服务令牌，至少 32 字节>
RISK_SERVICE_URL=https://...
RISK_SERVICE_TOKEN=<独立服务令牌，至少 32 字节>
FIXED_EGRESS_IP_CONFIGURED=true
LIVE_TRADING_ENABLED=false
```

`LIVE_TRADING_ENABLED` 默认保持关闭。启用顺序固定为：

1. 只读帐号权限与时间同步。
2. 余额、负债和持仓快照。
3. User Data Stream 与 REST 补偿。
4. 最小金额现货人工订单。
5. 全仓杠杆人工订单。
6. 逐仓杠杆人工订单。
7. U 本位永续人工订单。
8. 完整对账和故障演练。
9. 白名单自动交易。

每一步均需独立审批和对账证据；任何未知订单未关闭前不得进入下一阶段。

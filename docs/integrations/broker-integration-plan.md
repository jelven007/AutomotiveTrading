# 外部交易通道接入计划

> 文档编号：QT-INT-001
>
> 版本：1.1-draft

## 1. 原则

- 只使用官方授权接口和测试账号。
- 不通过 UI 自动化或逆向协议替代正式 API。
- 每个通道先完成能力矩阵，再实现 Adapter。
- 测试、模拟、实盘环境使用不同凭据。
- 未取得权限时使用 Stub，不宣称完成真实接入。

## 2. 富途实盘

### 富途商务与权限

- 确认账户司法辖区与可交易市场。
- 完成 OpenAPI 问卷和协议。
- 确认云端 OpenD 与 SaaS 使用条款。
- 获取模拟或测试账户。
- 确认行情套餐、订阅额度和限频。

### 富途技术验证

- OpenD 部署、升级、登录和保活。
- 交易解锁及 MFA/设备要求。
- 账户、资金、持仓查询。
- 下单、撤单、部分成交和拒单。
- 推送断线、补偿查询和对账。
- A/H/美股能力差异。

## 3. 同花顺模拟盘

### 同花顺商务与权限

- 确认接入产品为 SuperMind 或智能交易模拟盘。
- 确认是否支持服务端 SaaS 调用。
- 获取接口文档、测试账号和技术支持。
- 确认数据和模拟交易授权边界。

### 同花顺技术验证

- 账户创建和绑定。
- 策略发布或订单接口方式。
- 委托、撤单、成交和持仓。
- 回报模式与断线补偿。
- 限频、交易日历和错误码。
- 模拟盘重置和数据保留规则。

## 4. 财信证券实盘

### 财信商务与权限

- 由券商确认 QMT、PTrade、ATX 或其他正式方案。
- 确认个人或机构准入条件和资产门槛。
- 确认是否允许 SaaS 服务代用户调用。
- 获取正式文档、测试账号和联系人。

### 财信技术验证

- Windows 专机或网关要求。
- IP 白名单和网络专线。
- 登录、保活和交易时段。
- 账户、资金、持仓和可卖数量。
- 下单、撤单、成交回报和查询。
- 版本升级、错误码和限频。

## 5. 长桥实盘

### 长桥商务与权限

- 确认账户司法辖区与港股、美股交易权限。
- 申请 OpenAPI 权限和测试账号。
- 确认行情订阅、服务端部署、IP 白名单和接口限频。
- 确认 SaaS 代用户调用及凭据托管条款。

### 长桥技术验证

- OAuth/API Key 认证、连接保活和权限查询。
- 账户、资金、持仓和购买力查询。
- 下单、撤单、成交推送和订单补偿查询。
- 交易时段、订单类型、碎股和币种差异。
- 断线恢复、重复回报、对账和错误码映射。

官方资料：

- <https://open.longbridge.com/docs>

## 6. 币安生产交易

### 6.1 一期产品范围

- 生产现货。
- 全仓杠杆。
- 逐仓杠杆。
- U 本位永续合约。
- 不包含币本位合约和期权。

### 6.2 账户与凭据

- 仅租户管理员可绑定，操作要求近期 MFA。
- 优先使用 Ed25519 API Key，兼容 HMAC/RSA。
- Key 与私钥/Secret 写入 KMS，业务库只保存引用和脱敏指纹。
- API Key 必须绑定 Connector 固定出口 IP。
- 查询权限和交易权限分别检查；检测到提现权限时拒绝绑定。
- 首次启用生产写权限必须再次 MFA，并保留风险确认审计。
- Connector 只允许访问币安官方生产域名。

### 6.3 现货验证

- 服务器时间同步和签名校验。
- 账户余额、开放委托、历史委托和成交。
- 市价单、限价单、撤单和订单查询。
- `clientOrderId` 幂等映射、限频和超时未知状态处理。
- User Data Stream 续期、断线恢复和 REST 补偿。

### 6.4 全仓与逐仓杠杆验证

- 全仓账户资产、负债、利息、净资产和风险率。
- 逐仓交易对资产、负债、风险状态和预估强平价。
- 现货与杠杆账户划转。
- 借款、还款、最大可借额度和借款库存不足。
- 全仓/逐仓订单、自动借还款选项和撤单后负债核验。
- `MARGIN_CALL`、`PRE_LIQUIDATION`、`FORCE_LIQUIDATION`
  状态触发保护模式。

### 6.5 U 本位永续验证

- 账户余额、可用余额、维持保证金和未实现盈亏。
- 单向/双向持仓模式。
- 全仓/逐仓保证金模式和杠杆倍数。
- 市价/限价开仓、`reduceOnly` 减仓、撤单和成交。
- 标记价格、指数价格、强平价、资金费率和 ADL 风险。
- 用户数据流续期、订单/账户更新去重和 REST 对账。

### 6.6 正式资金准入

- 账户主体所在司法辖区允许使用相关产品。
- 完成服务条款、法律、合规和税务评审。
- 生产 Key 通过权限最小化和泄漏扫描。
- 完成只读、最小金额人工交易、撤单、减仓和对账验证。
- 自动交易必须经过回测、模拟、风险测评、白名单和 MFA。
- 异常时只允许撤单、还款、追加保证金或减仓。

官方资料：

- <https://developers.binance.com/docs/binance-spot-api-docs/rest-api/request-security>
- <https://developers.binance.com/docs/binance-spot-api-docs/rest-api/account-endpoints>
- <https://developers.binance.com/docs/binance-spot-api-docs/faqs/api_key_types>
- <https://developers.binance.com/docs/margin_trading/account/Query-Cross-Margin-Account-Details>
- <https://developers.binance.com/docs/margin_trading/account/Query-Isolated-Margin-Account-Info>
- <https://developers.binance.com/docs/margin_trading/borrow-and-repay/Margin-Account-Borrow-Repay>
- <https://developers.binance.com/docs/margin_trading/trade/Margin-Account-New-Order>
- <https://developers.binance.com/docs/derivatives/usds-margined-futures/account/rest-api/Account-Information-V3>
- <https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Order>

## 7. 统一能力矩阵模板

| 能力 | 同花顺 | 财信 | 富途 | 长桥 | 币安 |
| --- | --- | --- | --- | --- | --- |
| 页面 | 沪深 | 沪深 | 港美 | 港美 | 币安 |
| 支持环境 | 模拟 | 待确认 | 待确认 | 待确认 | 生产 |
| A 股 | 待确认 | 待确认 | 待确认 | 否 | 否 |
| 港股 | 否 | 否 | 待确认 | 待确认 | 否 |
| 美股 | 否 | 否 | 待确认 | 待确认 | 否 |
| 现货 | 不适用 | 不适用 | 不适用 | 不适用 | 是 |
| 全仓杠杆 | 不适用 | 不适用 | 不适用 | 不适用 | 是 |
| 逐仓杠杆 | 不适用 | 不适用 | 不适用 | 不适用 | 是 |
| U 本位永续 | 不适用 | 不适用 | 不适用 | 不适用 | 是 |
| 推送回报 | 待确认 | 待确认 | 待确认 | 待确认 | 是 |
| 客户端幂等号 | 待确认 | 待确认 | 待确认 | 待确认 | 是 |
| 云端部署 | 待确认 | 待确认 | 待确认 | 待确认 | 是 |

## 8. Adapter 验收

- 通过统一契约测试。
- 通过全订单状态测试。
- 通过断连、超时和重复回报测试。
- 通过资金、持仓和成交对账。
- 币安通过现货、全仓杠杆、逐仓杠杆和 U 本位永续专项测试。
- 杠杆负债、利息、强平状态和合约资金费率可对账。
- 凭据不进入日志。
- 能独立启停和回滚。
- 发布能力矩阵和已知限制。

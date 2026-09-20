# 交易帐号与币安接入设计

> 文档编号：QT-DES-TRD-001
>
> 状态：基础能力已实现，待真实资金生产验收
>
> 日期：2026-09-19

**Superseded（2026-09-20）：** 本文中的币安设计已由
[`QT-DES-BIN-NT-001`](2026-09-20-binance-nautilustrader-integration-design.md)
取代。本文仅保留历史背景，不再作为币安实现基线。

## 1. 目标与范围

交易一级菜单下固定提供三个二级页面：

| 页面 | 一期帐号通道 |
| --- | --- |
| 沪深 | 同花顺、财信证券 |
| 港美 | 富途、长桥 |
| 币安 | 币安 |

每个页面右上角提供“添加帐号”。证券通道在正式权限到位前允许使用明确标记的
Stub；币安按官方生产 API 设计，支持真实资金。

币安一期范围：

- 生产现货。
- 全仓杠杆。
- 逐仓杠杆。
- U 本位永续合约。

币本位合约、期权和未明确列出的衍生品不在一期范围。

## 2. 页面设计

### 2.1 路由

```text
/trading                -> 重定向到 /trading/cn
/trading/cn             -> 沪深
/trading/hk-us          -> 港美
/trading/binance        -> 币安
```

交易页使用紧凑的二级标签导航，不新增侧边栏。页面头部左侧展示当前市场组、
帐号数量和连接摘要，右侧固定“添加帐号”、对账和急停操作。

### 2.2 帐号列表

帐号列表按可扫描表格展示：

- 帐号别名和通道。
- 模拟/生产环境。
- 外部帐号脱敏标识。
- 已启用产品 Scope。
- 只读/可交易状态。
- 连接和数据新鲜度。
- 风险状态。
- 最近同步时间。
- 测试、启停、轮换凭据、删除等操作。

无帐号时显示空状态和“添加帐号”，不展示虚构资产。

### 2.3 添加帐号流程

证券页面先选择允许的通道，再按通道显示字段。未取得正式接口权限的通道保存
为 `stub` 或 `pending_authorization`，不能宣称连接成功。

币安使用分步流程：

1. 选择生产环境和凭据类型，默认 Ed25519。
2. 填写 API Key 与私钥/Secret，并确认固定出口 IP 白名单。
3. 选择现货、全仓杠杆、逐仓杠杆、U 本位永续 Scope。
4. 后端检查服务器时间、身份、权限、提现权限和帐号资格。
5. 凭据写入 KMS，页面只显示指纹和最后四位。
6. 帐号以只读状态连接。
7. 用户完成近期 MFA 和风险确认后，按 Scope 启用生产写权限。

浏览器不得持久化币安凭据。关闭弹窗、成功提交或失败后都必须清空敏感字段。

### 2.4 币安工作区

币安页面内部使用“现货、全仓、逐仓、U 本位”产品标签：

- 现货：余额、开放委托、最近成交和现货下单。
- 全仓：净资产、总负债、利息、风险率、借还款和杠杆订单。
- 逐仓：按交易对查看资产、负债、风险状态、强平价和杠杆订单。
- U 本位：保证金余额、持仓、未实现盈亏、强平价、杠杆和开平仓。

订单表必须持续显示帐号 Scope、环境、方向、开平仓语义和风险状态，禁止只用
颜色区分现货、杠杆和合约。

## 3. 服务边界

```text
Web
  -> API Gateway / BFF
  -> Trading Service
       -> Risk Service
       -> Outbox / Kafka
       -> Binance Connector
            -> Spot REST + User Data Stream
            -> Margin REST + Trade/Risk Data Stream
            -> USD-M REST + User Data Stream
            -> KMS Credential Provider
  -> Reconciliation Service
```

Web、策略和 Trading Service 不直接访问币安。Binance Connector 独立部署，
使用固定出口 IP 和最小 KMS 权限。查询、交易和帐号权限检查结果回传 Trading
Service；密钥不进入事件、日志或错误详情。

Connector 必须统一处理：

- Binance 服务器时间同步和签名。
- API 权重、UID 权重和订单速率限制。
- `clientOrderId` 与平台幂等键映射。
- User Data Stream 续期、断线恢复、事件去重和 REST 补偿。
- 币安错误码到平台稳定错误码的映射。

## 4. 币安产品规则

### 4.1 现货

- 查询账户余额、开放委托、历史订单和成交。
- 支持市价单、限价单和撤单。
- 下单前校验交易对状态、精度、最小数量和最小名义价值。
- 外部超时后标记 `unknown`，使用订单号或 `clientOrderId` 查询。

### 4.2 全仓与逐仓杠杆

- 全仓与逐仓分别建模，禁止共享风险快照。
- 逐仓请求必须绑定交易对。
- 借款前查询最大可借和库存；还款不得超过实际负债。
- 借还款、划转和订单使用不同幂等流水。
- 自动借还款为显式选项，默认关闭。
- 借还款存在待处理事务时串行等待，不自动并发重试。
- 进入追加保证金、预强平或强平状态后禁止扩大风险。

### 4.3 U 本位永续

- 同步单向/双向持仓模式、全仓/逐仓保证金模式和当前杠杆。
- 平台设置独立的最大杠杆上限，不能直接信任交易所允许值。
- 开仓与减仓使用明确语义；`reduceOnly` 不得导致反向持仓。
- 风控使用标记价格计算名义价值、保证金率和强平距离。
- 资金费率、手续费、已实现/未实现盈亏进入对账。
- ADL 风险或强平风险过高时进入保护模式。

## 5. 安全与生产准入

- 币安帐号主体和产品资格必须符合所在司法辖区、币安服务条款及当地法律。
- API Key 默认只读；交易权限按 Scope 单独启用。
- 检测到提现权限时拒绝绑定。
- 首次启用生产交易、借款、提高杠杆、开启自动交易和解除保护模式要求 MFA。
- 生产灰度顺序为：只读同步、最小金额现货、全仓、逐仓、U 本位。
- 每一步完成订单、成交、资产、负债、持仓和费用对账后才能进入下一步。
- 自动交易必须额外通过回测、模拟观察、风险测评、白名单和人工值守。

## 6. 错误处理

| 场景 | 系统行为 |
| --- | --- |
| 签名失败或时钟偏差 | 禁止交易，重新同步时间并告警 |
| Key 权限变化 | 切换只读或断开，禁止新订单 |
| 检测到提现权限 | 拒绝绑定或立即停用帐号 |
| API 限频 | 按官方窗口调度，不重试写订单 |
| 下单响应超时 | 标记 `unknown`，查询后人工处理 |
| User Data Stream 中断 | 暂停新增风险，REST 补偿并对账 |
| 借款库存不足 | 拒绝请求，不降级为其他资产 |
| 杠杆预强平/强平 | 保护模式，只允许降低风险 |
| 合约 ADL/强平风险过高 | 禁止开仓和提高杠杆 |

## 7. 测试与验收

必须覆盖：

- 三个交易子页面及通道白名单。
- 币安 Key 权限、提现权限拒绝、IP 白名单、MFA 和密钥不可回显。
- 现货最小金额下单、撤单、成交和对账。
- 全仓/逐仓划转、借款、还款、交易和风险隔离。
- U 本位持仓模式、保证金模式、杠杆、开平仓和 `reduceOnly`。
- 超时未知状态、重复事件、流断线、限频和重启恢复。
- 预强平、强平、ADL 和保护模式。

生产验收证据不得包含完整 API Key、Secret、私钥、UID 或完整资产明细。

## 8. 官方接口基线

- <https://developers.binance.com/docs/binance-spot-api-docs/faqs/api_key_types>
- <https://developers.binance.com/docs/binance-spot-api-docs/rest-api/request-security>
- <https://developers.binance.com/docs/binance-spot-api-docs/rest-api/account-endpoints>
- <https://developers.binance.com/docs/margin_trading/account/Query-Cross-Margin-Account-Details>
- <https://developers.binance.com/docs/margin_trading/account/Query-Isolated-Margin-Account-Info>
- <https://developers.binance.com/docs/margin_trading/borrow-and-repay/Margin-Account-Borrow-Repay>
- <https://developers.binance.com/docs/margin_trading/trade/Margin-Account-New-Order>
- <https://developers.binance.com/docs/derivatives/usds-margined-futures/account/rest-api/Account-Information-V3>
- <https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/rest-api/New-Order>
- <https://developers.binance.com/docs/derivatives/usds-margined-futures/user-data-streams/Keepalive-User-Data-Stream>

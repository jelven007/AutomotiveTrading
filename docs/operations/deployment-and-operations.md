# 部署与运维方案

> 文档编号：QT-OPS-001
>
> 版本：1.1-draft

## 1. 环境

- Development：开发联调，外部交易全部 Stub。
- Integration：共享集成环境，币安使用 Testnet。
- UAT：用户验收、券商测试环境和币安生产只读帐号。
- Pre-production：生产同构。
- Production：火山引擎中国区，按白名单启用币安小额真实资金。

各环境使用独立 VPC、数据库、Topic、Bucket、密钥和访问身份。

当前 M2 的开发、演示和集成验证可使用
[Ubuntu 单机部署指南](ubuntu-single-node-deployment.md)。该方案不替代以下生产架构。

`trading`、`risk` 和 `kms-adapter` 已纳入可选的 `binance-readonly` UAT
Profile，默认诊断端口分别为 `8004`、`8005` 和 `8006`，且只绑定宿主机回环
地址。默认部署不会启动该 Profile。

### 1.1 币安只读 UAT

先执行常规初始化：

```bash
bash scripts/deploy.sh init
```

然后在 `infra/compose/.env.deploy` 中配置：

```text
KMS_KEY_ID=<火山引擎 KMS 主密钥 ID>
KMS_REGION=cn-beijing
VOLCENGINE_ACCESS_KEY=<由运行环境安全注入>
VOLCENGINE_SECRET_KEY=<由运行环境安全注入>
VOLCENGINE_SESSION_TOKEN=<使用临时凭据时填写>
FIXED_EGRESS_IP_CONFIGURED=true
PUBLIC_BASE_URL=https://<已完成 TLS 终止的访问域名>
```

只有确认 ECS 固定出口 IP 已加入币安 API Key 白名单后，才能把
`FIXED_EGRESS_IP_CONFIGURED` 改为 `true`；只有公网入口已经由负载均衡或反向
代理完成 HTTPS 终止后，才能填写 `PUBLIC_BASE_URL`。启动命令：

```bash
bash scripts/deploy.sh readonly-up
```

该命令会创建或确认 `qt_kms`、`qt_risk`、`qt_trading` 数据库，执行三个服务的
迁移并启动只读链路。`LIVE_TRADING_ENABLED` 固定为 `false`，不能通过该 Profile
启用实盘写操作。UAT Docker 网络允许显式内部 HTTP；正式生产必须改为内部 HTTPS，
不得开启 `ALLOW_INSECURE_INTERNAL_HTTP`。

## 2. VKE 部署

- Gateway、Web BFF 和核心服务跨可用区部署。
- Broker Connector 使用独立命名空间和节点池。
- Backtest Runner 使用独立节点池、配额和 NetworkPolicy。
- 每个服务配置资源请求、限制、健康检查和 PodDisruptionBudget。
- 数据库与消息系统优先使用托管服务。

## 3. 发布

- 主干开发与短生命周期分支。
- 镜像不可变并使用 Commit SHA 标记。
- CI 完成测试、扫描、SBOM 和签名。
- CD 先部署 Integration，再 UAT、Pre-prod 和 Production。
- 生产使用金丝雀或蓝绿发布。
- 数据库迁移必须向前兼容，应用回滚不依赖降级 Schema。

## 4. 配置与密钥

- 普通配置使用配置中心。
- Secret 使用 KMS/密钥管理。
- 禁止在仓库、镜像和 Helm Values 中存放明文密钥。
- 生产变更需审批并保留审计。
- Broker Connector 的出口和凭据单独管理。
- Binance Connector 使用独立服务身份、固定出口 EIP 和域名白名单。
- 币安生产 Key 优先采用 Ed25519，私钥仅由 Connector 从 KMS 临时读取。
- 自动校验 Key 无提现权限；查询、现货、杠杆和合约权限分别记录。

## 5. 监控与告警

### P0

- 发现重复实盘订单。
- 租户数据泄漏。
- 订单事件丢失。
- 账实重大差异。
- 密钥泄漏。
- 风控不可用但仍有订单提交。
- 币安帐号进入预强平、强平或 ADL 高风险状态。
- 检测到币安 Key 具有提现权限或固定出口 IP 不匹配。

### P1

- 券商持续断连。
- 币安用户数据流断开且 REST 补偿失败。
- 杠杆风险率或合约强平距离低于阈值。
- 币安 API 限频持续触发。
- 行情严重延迟。
- `unknown` 订单超过阈值。
- Kafka 大量积压。
- MySQL 不可用。

### P2

- 模型错误率或成本异常。
- 回测队列超时。
- 非核心查询降级。

## 6. 备份与恢复

- MySQL 持续备份与时间点恢复。
- TOS 开启版本和生命周期。
- Kafka 按业务 RPO 配置保留。
- ClickHouse 定期快照。
- KMS 密钥恢复流程独立演练。
- 每季度进行恢复演练并记录 RPO/RTO。

## 7. 事件响应

1. 告警触发并分级。
2. 指定 Incident Commander。
3. 交易风险优先执行急停或保护模式。
4. 保留日志、Trace、订单和券商证据。
5. 恢复后完成对账。
6. 形成复盘、整改项和截止时间。

## 8. 常用 Runbook

必须单独维护：

- 券商断连。
- 币安 User Data Stream 断线与 Listen Key 失效。
- 币安 API Key 吊销、权限变化和紧急轮换。
- 币安杠杆追加保证金、预强平和强平。
- 币安 U 本位永续 ADL、资金费率异常和强平保护。
- 币安订单超时、状态未知和 REST 补偿对账。
- 行情数据延迟。
- 模型供应商故障。
- 未知订单。
- 重复订单疑似事件。
- 对账差异。
- 租户越权疑似事件。
- KMS 或密钥轮换故障。
- Kafka 积压。
- 数据库切换。
- 全局急停与恢复。

## 9. 容量与成本

- 以租户、策略、标的、触发频率估算模型调用量。
- 回测计算与在线交易节点分池。
- 模型费用、行情费用和券商通道费用独立计量。
- 币安按现货、全仓杠杆、逐仓杠杆和 U 本位永续分别统计请求权重、
  订单速率、流连接和对账成本。
- 设置租户硬配额和平台软告警。
- 每月评审单位策略、单位回测和单位订单成本。

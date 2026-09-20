# 部署与运维方案

> 文档编号：QT-OPS-001
>
> 版本：1.2-draft

币安单机部署和故障处理细节见
[`QT-OPS-BIN-NT-001`](binance-nautilustrader-runbook.md)。

## 1. 环境

- Development：开发联调，外部交易全部 Stub。
- Integration：共享集成环境，币安使用 Testnet。
- UAT：用户验收、券商测试环境和币安生产只读帐号。
- Pre-production：生产同构。
- Production：火山引擎中国区，按白名单启用币安小额真实资金。

各环境使用独立 VPC、数据库、Topic、Bucket、密钥和访问身份。

当前 M2 的开发、演示和集成验证可使用
[Ubuntu 单机部署指南](ubuntu-single-node-deployment.md)。该方案不替代以下生产架构。

币安目标部署使用可选的 `binance-trading` Profile，仅启动 `trading` 服务并在
进程内运行 NautilusTrader；不依赖 `risk` 和 `kms-adapter`。Trading 诊断端口
默认使用 `8004` 且只绑定宿主机回环地址。当前代码仍使用旧
`binance-readonly` Profile，迁移状态见
[`QT-INT-BIN-001`](../integrations/binance-production-readiness.md)。

### 1.1 币安 Nautilus UAT 目标

先执行常规初始化：

```bash
bash scripts/deploy.sh init
```

部署脚本生成：

```text
/opt/quant-trading/secrets/credential-master-key
```

该文件必须为 `root:root`、权限 `600`，并只读挂载到 Trading 容器。普通配置：

```text
BINANCE_CREDENTIAL_MASTER_KEY_FILE=/run/secrets/binance_credential_master_key
FIXED_EGRESS_IP_CONFIGURED=true
PUBLIC_BASE_URL=https://<已完成 TLS 终止的访问域名>
BINANCE_TESTNET=true
BINANCE_LIVE_TRADING_ENABLED=false
```

只有确认 ECS 固定出口 IP 已加入币安 API Key 白名单后，才能把
`FIXED_EGRESS_IP_CONFIGURED` 改为 `true`；只有公网入口已经由负载均衡或反向
代理完成可信 HTTPS 终止后，才能填写 `PUBLIC_BASE_URL`。目标启动命令：

```bash
bash scripts/deploy.sh binance-up
```

该命令创建或确认 `qt_trading` 数据库、执行 Trading 迁移并启动 Nautilus
Testnet 链路。生产写操作默认关闭，必须在 Testnet 和生产只读验收后显式启用。

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
- 币安使用 Trading 内部 Nautilus Runtime、固定出口 EIP 和域名白名单。
- 币安 HMAC/Ed25519 凭据使用本地主密钥 AES-256-GCM 加密入库。
- 主密钥只读挂载且权限为 `600`，必须与数据库分开备份。
- 币安 IP 白名单和禁止提现由管理员在控制台确认并记录。

## 5. 监控与告警

### P0

- 发现重复实盘订单。
- 租户数据泄漏。
- 订单事件丢失。
- 账实重大差异。
- 密钥泄漏。
- 风控不可用但仍有订单提交。
- 币安 U 本位帐号进入预强平、强平或 ADL 高风险状态。
- 怀疑币安 Key 权限、IP 白名单或凭据安全状态发生变化。

### P1

- 券商持续断连。
- 币安 Nautilus 私有流断开且执行对账失败。
- U 本位合约强平距离低于阈值。
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
- KMS 密钥恢复流程独立演练；币安本地主密钥与数据库执行配对恢复演练。
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
- 币安 Nautilus Spot/USD-M 客户端断线与恢复。
- 币安 API Key 吊销、权限变化和紧急轮换。
- 币安 U 本位永续 ADL、资金费率异常和强平保护。
- 币安订单超时、`pending_reconciliation` 和执行对账。
- 币安活动帐号切换失败。
- 币安本地主密钥丢失或权限异常。
- 行情数据延迟。
- 模型供应商故障。
- 未知订单。
- 重复订单疑似事件。
- 对账差异。
- 租户越权疑似事件。
- KMS 或本地主密钥轮换故障。
- Kafka 积压。
- 数据库切换。
- 全局急停与恢复。

## 9. 容量与成本

- 以租户、策略、标的、触发频率估算模型调用量。
- 回测计算与在线交易节点分池。
- 模型费用、行情费用和券商通道费用独立计量。
- 币安按现货和 U 本位分别统计请求、订单速率、流连接和对账成本。
- 设置租户硬配额和平台软告警。
- 每月评审单位策略、单位回测和单位订单成本。

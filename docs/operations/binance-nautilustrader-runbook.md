# 币安 NautilusTrader 运维与排障手册

> 文档编号：QT-OPS-BIN-NT-001
>
> 版本：1.0
>
> 日期：2026-09-20
>
> 状态：待实施验证

## 1. 适用范围

本手册适用于个人单用户 ECS 上的币安现货与 U 本位服务。运行组件为 Web、
Identity、Trading、MySQL 和 NautilusTrader，不依赖币安官方 SDK、云 KMS、
独立 Risk Service 或 Kafka。

## 2. 部署前检查

### 2.1 主机和入口

- 公网入口使用可信 HTTPS 证书。
- Trading 端口仅绑定 `127.0.0.1` 或 Docker 内网。
- ECS 使用固定出口 IP。
- ECS 到 Binance Spot/USD-M REST 和 WebSocket 均可用。

### 2.2 币安帐号

- API Key 已绑定固定出口 IP。
- 开启读取、现货交易和 U 本位交易所需权限。
- 禁止提现、通用划转和不需要的权限。
- 帐号已完成 U 本位资格确认。

由于系统不引入第二套 Binance 客户端，以上权限在币安控制台人工确认并记录时间。

### 2.3 本地主密钥

目标路径：

```text
/opt/quant-trading/secrets/credential-master-key
```

要求：

- 内容为 32 个随机字节，使用 Base64 编码保存。
- 所有者为 `root:root`。
- 权限为 `600`。
- 只读挂载到 Trading 容器。
- 备份与数据库备份分开保存。

禁止将主密钥写入 Git、镜像、Compose YAML、普通 `.env` 或日志。

## 3. 启动检查

建议命令：

```bash
bash scripts/deploy.sh binance-up
bash scripts/deploy.sh status
curl -fsS http://127.0.0.1:8004/health
curl -fsS http://127.0.0.1:8004/api/v1/trading/binance/status
```

预期：

- 服务健康。
- 未配置活动帐号时状态为 `inactive`，而非进程失败。
- 配置活动帐号后 Spot 与 USD-M 分别进入 connecting、reconciling、ready。
- `accepting_orders` 只有在对账完成且未急停时为 true。

## 4. 帐号操作

### 4.1 添加

1. 登录系统并完成近期 MFA。
2. 进入“交易 → 币安”。
3. 点击“添加帐号”并输入凭据。
4. 确认 IP 白名单和禁止提现。
5. 保存后检查脱敏指纹和产品测试结果。

### 4.2 切换

切换前确认：

- 当前没有 `pending_submit`、`cancel_pending` 或
  `pending_reconciliation` 订单。
- 没有未处理的数据库错误。
- 操作者清楚目标帐号别名和指纹。

切换期间不得刷新页面后重复点击。超过 60 秒仍未完成时按“帐号切换失败”处理。

### 4.3 更新和删除

- 更新凭据会创建新密文并覆盖旧密文。
- 更新后必须重新测试并激活。
- 活动帐号必须先停用。
- 有未决订单的帐号禁止删除。

## 5. 状态说明

| 状态 | 含义 | 是否允许交易 |
| --- | --- | --- |
| `inactive` | 无活动帐号 | 否 |
| `connecting` | 正在连接 | 否 |
| `reconciling` | 正在恢复账户事实 | 否 |
| `ready` | 两个客户端均可用 | 是 |
| `partial` | 仅一个产品可用 | 仅可用产品 |
| `stale` | 私有数据超时 | 否 |
| `switching` | 正在切换帐号 | 否 |
| `error` | 需要人工处理 | 否 |
| `emergency_stopped` | 急停生效 | 否 |

## 6. 常见故障

### 6.1 凭据无法解密

症状：

- `binance.credential_store_unavailable`
- `binance.credential_invalid`

检查：

```bash
stat -f '%Sp %Su:%Sg %N' /opt/quant-trading/secrets/credential-master-key
docker inspect qt-trading --format '{{json .Mounts}}'
```

处理：

- 确认主密钥文件存在、权限为 `600`、只读挂载。
- 确认恢复数据库时同时恢复了对应主密钥。
- 不尝试猜测或重置主密钥；无法恢复时重新录入帐号凭据。

### 6.2 Binance 网络不可达

症状：

- `binance.disconnected`
- DNS 解析异常、TLS 超时或连接重置。

检查：

```bash
getent ahostsv4 api.binance.com
getent ahostsv4 fapi.binance.com
curl -4Iv --max-time 10 https://api.binance.com/api/v3/time
curl -4Iv --max-time 10 https://fapi.binance.com/fapi/v1/time
```

不要通过关闭 TLS 校验、固定 CDN IP 或无限增加超时规避问题。保存 DNS、TCP 和
TLS 证据并联系网络管理员。

### 6.3 认证失败

症状：`binance.authentication_failed`。

检查：

- 当前帐号指纹是否与币安控制台一致。
- 固定出口 IP 是否仍在白名单。
- Key 是否被删除、过期或修改权限。
- 系统时间是否同步。

更新凭据后重新测试，不要在日志或工单中粘贴完整 Key。

### 6.4 Spot 或 Futures 单侧断开

症状：状态为 `partial`。

处理：

- 确认具体产品状态和最后错误。
- 冻结故障产品的新订单。
- 允许另一产品继续只读；是否继续写入由人工判断。
- 恢复后等待产品级对账完成。

### 6.5 未决订单

症状：订单为 `pending_reconciliation`。

处理：

1. 不使用新幂等键重提相同订单。
2. 根据 Client Order ID 和 Venue Order ID 查询。
3. 等待私有流或启动手工对账。
4. 只有确认交易所不存在订单后，才能由用户创建新订单。

### 6.6 帐号切换失败

检查：

- 旧节点是否仍在 stopping。
- 是否存在未决订单。
- 新帐号是否认证失败。
- Spot/USD-M 对账是否完成。

不要同时启动第二个 LiveNode。清理失败节点后重新执行切换。

### 6.7 杠杆或保证金模式失败

常见原因：

- 存在不允许切换的持仓或开放订单。
- 杠杆超出交易所或本地限制。
- symbol 使用了现货格式而不是 Nautilus 永续格式。

失败后读取交易所实际状态，禁止仅修改本地显示。

## 7. 脱敏诊断包

诊断命令应输出：

- 应用、Python 和 Nautilus 版本。
- Spot/USD-M 连接与对账状态。
- 最后事件时间和数据新鲜度。
- 未决订单数量及脱敏 ID。
- DNS、TCP、TLS 探测结果。
- 主密钥文件权限，不输出文件内容。

诊断包不得包含：

- API Key、Secret、私钥、密文或 nonce。
- 完整账户 UID。
- 完整资产和持仓明细。
- JWT、Cookie 或数据库密码。

## 8. 备份与恢复

- MySQL 和主密钥必须作为同一恢复点管理，但分开存放。
- 恢复后先启动只读模式并完成对账。
- 对账前保持急停。
- 每季度验证数据库与主密钥配对恢复。

## 9. 升级 NautilusTrader

1. 阅读目标版本 changelog。
2. 更新精确版本和 lockfile。
3. 执行单元及组件测试。
4. 执行 Spot/USD-M Testnet 生命周期。
5. 执行断线、重启和未决订单恢复。
6. 观察 Testnet 24 小时。
7. 生产只读灰度后再恢复写入。

禁止在生产机器直接执行未锁版本升级。

## 10. 事件响应

以下情况立即急停：

- 怀疑凭据泄漏。
- 出现重复订单。
- 对账无法收敛。
- 持仓或余额与币安显著不一致。
- 高杠杆或强平风险超出本地限制。
- 活动帐号身份无法确认。

急停后保留日志和数据库快照，先确认交易所事实，再决定恢复或轮换凭据。

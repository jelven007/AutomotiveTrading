# B Demo NautilusTrader 运维与排障手册

> 文档编号：QT-OPS-BIN-NT-001
>
> 版本：3.0
>
> 日期：2026-09-22
>
> 状态：Demo-only 基线完成，模拟账号验收待执行

## 1. 适用范围

本手册适用于个人单用户 ECS 上的 B Demo 现货与 U 本位服务。运行组件仅为
Web、Identity、Trading、MySQL 和 NautilusTrader。当前版本不能连接主网。

## 2. 部署前检查

### 2.1 主机和入口

- 公网入口使用可信 HTTPS 证书。
- Trading 端口仅绑定 `127.0.0.1` 或 Docker 内网。
- ECS 到 B Spot/USD-M Demo REST 和 WebSocket 均可用。

### 2.2 B 模拟帐号

- 只使用跨产品共享的一套 Demo Key，并开启读取与所需模拟交易权限。
- 禁止提现、通用划转和不需要的权限。
- 帐号已完成 U 本位资格确认。

系统固定通过 Spot Demo `/api/v3/account` 验证签名和交易能力；Spot 与 USD-M
Runtime 首次读取共同完成候选账号验收。当前 Demo 接入不要求固定出口 IP 或
IP 白名单。

### 2.3 本地主密钥

目标路径：

```text
/opt/quant-trading/secrets/credential-master-key
```

要求：

- 内容为 32 个原始随机字节，不进行 Base64 文本编码。
- 所有者 UID 与 Trading 容器用户一致；当前固定镜像为 `100:101`。
- 权限为 `600`。
- 只读挂载到 Trading 容器。
- 备份与数据库备份分开保存。

禁止将主密钥写入 Git、镜像、Compose YAML、普通 `.env` 或日志。

首次创建：

```bash
sudo install -d -m 700 /opt/quant-trading/secrets
sudo sh -c \
  'umask 077; openssl rand 32 > /opt/quant-trading/secrets/credential-master-key'
sudo chown 100:101 /opt/quant-trading/secrets/credential-master-key
sudo chmod 600 /opt/quant-trading/secrets/credential-master-key
sudo test "$(wc -c < /opt/quant-trading/secrets/credential-master-key)" -eq 32
```

在 `infra/compose/.env.deploy` 中确认：

```text
BINANCE_CREDENTIAL_MASTER_KEY_FILE=/opt/quant-trading/secrets/credential-master-key
BINANCE_CREDENTIAL_MASTER_KEY_UID=100
SINGLE_OWNER_MODE=true
BINANCE_ENVIRONMENT=demo
DEMO_TRADING_ENABLED=false
PUBLIC_BASE_URL=https://<公网入口>
```

下单接口完成前保持 `DEMO_TRADING_ENABLED=false`。当前代码没有主网 URL 或
主网启用开关。

## 3. 启动检查

建议命令：

```bash
bash scripts/deploy.sh up
bash scripts/deploy.sh status
curl -fsS http://127.0.0.1:8004/health/live
curl -fsS http://127.0.0.1:8004/health/ready
curl -fsS http://127.0.0.1:8004/health/binance
curl -fsS http://127.0.0.1:8004/api/v1/trading/health
curl -fsS -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  http://127.0.0.1:8004/api/v1/trading/binance/account
curl -fsS -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  'http://127.0.0.1:8004/api/v1/trading/binance/overview?refresh=true'
```

预期：

- 服务健康。
- `/health/binance` 分别返回 API、Spot 和 USD-M 状态，不返回资产明细。
- 未绑定帐号时返回 `binance.account_missing`，而非进程失败。
- 绑定后 Spot 与 USD-M 状态分别展示。
- 绑定后重启 Trading，唯一 Runtime 会从加密凭据自动恢复。
- `DEMO_TRADING_ENABLED=false` 时下单写接口返回
  `trading.demo_disabled`。
- 第二位用户注册返回 `registration.closed`。

`up` 启动 MySQL、Identity、Trading、Nautilus Runtime 和 Web。

### 3.1 Demo 真实验收

Demo 用例默认跳过。只有明确准备好模拟 Key 和独立验收账号后才执行：

```bash
export RUN_BINANCE_DEMO_TESTS=true
export BINANCE_UAT_BASE_URL=https://<公网入口>
export BINANCE_UAT_BEARER_TOKEN=<短期访问令牌>
export BINANCE_DEMO_API_KEY=<Demo Key>
export BINANCE_DEMO_API_SECRET=<Demo Secret>
uv run pytest tests/integration/binance/test_demo_overview.py -v
unset BINANCE_UAT_BEARER_TOKEN BINANCE_DEMO_API_KEY \
  BINANCE_DEMO_API_SECRET
```

该用例会替换当前用户的唯一 B 模拟账号。测试验证账号环境、Spot、USD-M 和写入
关闭门禁；余额与持仓数值仍需在 Demo 控制台人工交叉核对。

### 3.2 2026-09-21 部署记录

已完成：

- Identity 数据库待迁移至 `0002_single_system_owner`，Trading 数据库待迁移至
  `0005_global_binance_account`。
- Identity、Trading、Web 容器健康，主密钥以只读方式挂载。
- 主密钥权限为 `600`，所有者为 `100:101`，容器内可读。
- `BINANCE_ENVIRONMENT=demo`，Runtime 不能构造主网客户端。
- `DEMO_TRADING_ENABLED=false`，下单探测返回
  `trading.demo_disabled`。
- 未绑定账号的查询返回 `binance.account_missing`。

未通过：

- 尚未记录 ECS 到 `demo-api.binance.com` 和 `demo-fapi.binance.com` 的完整
  REST/WebSocket 验收结果。
- `https://118.196.108.119` 当前证书链不受客户端信任。
- 未提供显式 Demo API 凭据，真实集成测试按设计跳过。

解决出口线路、可信 HTTPS 入口并提供专用 Demo Key 前，不实现模拟下单。

## 4. 帐号操作

界面将 Binance 简称为“B”，以下步骤中的按钮和区块名称均按当前界面记录。

### 4.1 添加

1. 登录系统。
2. 进入「交易」页右侧的「资产」区块。
3. 在 USDT 未连接摘要卡中点击「账号」，并输入凭据。
4. 保存后检查脱敏指纹、权限和账户查询结果。

### 4.2 重新绑定

重新绑定使用同一表单。系统必须先验证新权限和候选 Nautilus Runtime，再覆盖
原记录：

- 验证成功：切换 Runtime、删除旧密文，页面仍只有一个帐号。
- 验证失败：保留旧帐号、旧密文和旧 Runtime。

不得先删除旧帐号再测试新凭据。

### 4.3 删除

- 删除前完成 TOTP 验证，确保 MFA 时间不超过 5 分钟。
- 当前删除时先停止 Runtime，再删除帐号和密文。
- 模拟下单阶段存在 `pending_reconciliation` 订单时禁止删除。

## 5. 状态说明

| 状态 | 含义 | 是否允许交易 |
| --- | --- | --- |
| `unbound` | 未绑定帐号 | 否 |
| `connecting` | 正在连接 | 否 |
| `ready` | 两个客户端均可查询 | Demo 写入门禁决定 |
| `partial` | 仅一个产品可查询 | 禁止故障产品模拟写入 |
| `stale` | 账户状态超时 | 否 |
| `error` | 需要人工处理 | 否 |

## 6. 常见故障

### 6.1 凭据无法解密

症状：

- `binance.credential_store_unavailable`
- `binance.credential_invalid`

检查：

```bash
stat -c '%A %u:%g %s %n' /opt/quant-trading/secrets/credential-master-key
docker inspect quant-trading-saas-trading-1 --format '{{json .Mounts}}'
```

处理：

- 确认主密钥文件存在、权限为 `600`、所有者 UID 为 `100`、只读挂载。
- 确认恢复数据库时同时恢复了对应主密钥。
- 不尝试猜测或重置主密钥；无法恢复时重新录入帐号凭据。

### 6.2 Binance 网络不可达

症状：

- `binance.disconnected`
- DNS 解析异常、TLS 超时或连接重置。

检查：

```bash
getent ahostsv4 demo-api.binance.com
getent ahostsv4 demo-fapi.binance.com
curl -4Iv --max-time 10 https://demo-api.binance.com/api/v3/time
curl -4Iv --max-time 10 https://demo-fapi.binance.com/fapi/v1/time
```

不要通过关闭 TLS 校验、固定 CDN IP 或无限增加超时规避问题。保存 DNS、TCP 和
TLS 证据并联系网络管理员。

### 6.3 认证失败

症状：`binance.authentication_failed`。

检查：

- 当前帐号指纹是否与 B Demo 控制台一致。
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

### 6.6 帐号重新绑定失败

检查：

- 新帐号权限是否安全。
- 候选 Spot/USD-M 客户端是否均完成首次读取。
- 数据库事务是否提交。

失败时不要删除旧帐号或停止旧 Runtime。确认候选 Runtime 已清理后重新绑定。

### 6.7 杠杆或保证金模式失败

常见原因：

- 存在不允许切换的持仓或开放订单。
- 杠杆超出交易所或本地限制。
- symbol 使用了现货格式而不是 Nautilus 永续格式。

失败后读取交易所实际状态，禁止仅修改本地显示。

## 7. 脱敏诊断包

诊断命令应输出：

- 应用、Python 和 Nautilus 版本。
- Spot/USD-M 连接和数据新鲜度。
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
- 恢复模拟交易前完成订单核对。
- 每季度验证数据库与主密钥配对恢复。

## 9. 升级 NautilusTrader

1. 阅读目标版本 changelog。
2. 更新精确版本和 lockfile。
3. 执行单元及组件测试。
4. 执行 Spot/USD-M Demo 生命周期。
5. 执行断线、重启和未决订单恢复。
6. 观察 Demo 24 小时。
7. 仅恢复 Demo 写入。

禁止在部署机器直接执行未锁版本升级。

## 10. 事件响应

Demo 交易阶段遇到以下情况立即关闭新订单：

- 怀疑凭据泄漏。
- 出现重复订单。
- 对账无法收敛。
- 持仓或余额与 B Demo 显著不一致。
- 杠杆或保证金模式与交易所不一致。
- 当前帐号身份无法确认。

关闭新订单后保留日志和数据库快照，先确认交易所事实，再决定恢复或轮换凭据。

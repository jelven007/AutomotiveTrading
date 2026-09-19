# 币安只读帐号模式系统接线设计

> 文档编号：QT-DES-BIN-RO-001
>
> 日期：2026-09-19
>
> 状态：已确认实施

## 1. 目标

在不开放实盘写操作的前提下，使用户能够使用币安生产 API Key 完成帐号绑定，
并由系统验证帐号身份、读取权限、产品可访问性和提现权限。

本阶段交付后：

- 币安 Key 只有读取权限时也能绑定为 `read_only` 帐号。
- 帐号启用交易时仍必须重新检查对应 Scope 的交易权限。
- KMS Adapter、Risk Service 和 Trading Service 可通过可选 UAT Compose Profile
  部署。
- Web 可将 `/api/v1/trading` 请求代理到 Trading Service。
- 默认云端部署不自动启用币安只读链路，必须显式执行 `readonly-up`。

真实余额和持仓的页面展示不属于本阶段；登录、注册和按需 MFA 已在后续实现中补齐。

## 2. 只读绑定语义

帐号绑定与交易启用使用不同校验：

- 绑定：通过 `/sapi/v1/account/apiRestrictions` 要求读取权限开启、IP 限制开启，
  提现、内部划转和通用划转权限关闭。
- 绑定：访问用户选中的现货、全仓、逐仓、U 本位接口，验证产品可用性，但不要求
  帐户接口中的 `canTrade=true`。
- 绑定成功：状态固定为 `read_only`，所有 Scope 固定为 `enabled=false`。
- 启用交易：要求近期 MFA、KMS、Risk、固定出口和全局交易开关全部就绪，并重新
  从 API Key 权限接口校验每个 Scope 的交易权限及交易权限有效期。

这样可以先使用真正的只读 Key 完成数据验证，避免为查看资产而提前授予交易权限。

## 3. 单机 UAT 拓扑

```text
Browser
  -> Web :80
       -> Identity :8000
       -> Trading :8000
            -> KMS Adapter :8000
                 -> Volcengine KMS
            -> Binance official HTTPS APIs
       -> Risk :8000
```

KMS、Risk、Trading 仅绑定宿主机回环地址用于诊断。Web 是唯一公网入口。内部
HTTP 仅允许在 `ENVIRONMENT=uat` 且显式开启配置时使用；生产环境仍强制 HTTPS。

## 4. 配置与启动

新增 `binance-readonly` Compose Profile，并由 `scripts/deploy.sh readonly-up`
显式启动。启动前检查：

- `KMS_KEY_ID` 已配置。
- 火山 KMS AK/SK 成对配置；STS Token 可选。
- `FIXED_EGRESS_IP_CONFIGURED=true`。
- KMS 与 Risk 服务令牌由部署脚本随机生成，不写入 Git。

新增 `qt_kms` 数据库。一次性数据库准备任务兼容已有 MySQL 数据卷，再依次运行
KMS、Risk、Trading 的 Alembic 迁移。

## 5. 安全边界

- `LIVE_TRADING_ENABLED=false` 固定为只读阶段默认值。
- API Key 强制启用 IP 限制并禁止提现、内部划转和通用划转权限；检测到不安全
  配置立即拒绝绑定或停用已绑定帐号。
- Binance Secret/私钥只经 Trading 内存传递到 KMS Broker，不进入业务数据库、
  日志或错误响应。
- KMS、Risk 使用不同随机服务令牌。
- `ALLOW_INSECURE_INTERNAL_HTTP` 在生产环境禁止启用。
- 本阶段不把 Risk/KMS API 暴露到公网。
- 页面允许提交真实凭据前，必须由外部负载均衡或反向代理完成公网 HTTPS 终止。

## 6. 验证

- 单元测试覆盖只读 Key 可绑定、交易启用仍拒绝权限不足的 Key。
- 契约测试覆盖内部 HTTP 只允许显式 UAT 配置和受信服务名。
- 部署测试覆盖 `qt_kms`、Compose Profile、迁移任务、随机令牌和 Web 代理。
- 执行 Python 全量测试、Ruff、Mypy、Bandit、前端 lint/test/build 和
  `docker compose config`。

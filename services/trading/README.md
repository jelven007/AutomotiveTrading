# trading

交易帐号、币安资金查询和订单执行服务。

当前支持：

- 币安生产现货、全仓杠杆、逐仓杠杆和 U 本位永续帐号权限检查。
- HMAC、RSA 和 Ed25519 REST 签名。
- 余额/持仓快照、杠杆借还、U 本位杠杆设置。
- 带幂等键、近期 MFA、风险审批和急停保护的下单与撤单。
- 超时订单进入 `unknown`，不会自动重放。

Run locally:

```bash
cp .env.example .env
uv run uvicorn trading.main:app --reload
```

本地凭据后端要求 `LOCAL_SECRET_ENCRYPTION_KEY` 为 Fernet Key。生产环境必须配置：

```text
ENVIRONMENT=production
SECRET_BACKEND=kms
KMS_URL=https://...
KMS_SERVICE_TOKEN=<至少 32 字节的独立服务令牌>
RISK_SERVICE_URL=https://...
RISK_SERVICE_TOKEN=<至少 32 字节的独立服务令牌>
ALLOW_INSECURE_INTERNAL_HTTP=false
FIXED_EGRESS_IP_CONFIGURED=true
LIVE_TRADING_ENABLED=true
```

缺少任一生产前置条件时，服务拒绝启用帐号或执行新增风险的写请求。首次配置时
`LIVE_TRADING_ENABLED` 应保持 `false`，先完成只读同步和人工灰度。

KMS Broker 的解析和删除请求始终同时传递 `tenant_id`；Risk 校验同时传递
`X-Service-Token` 与单次使用的 `X-Risk-Approval`。两个服务不可用、返回非
2xx 或响应格式错误时，Trading 均失败关闭。

单机 UAT Compose Profile 使用 Docker 私有网络和
`ALLOW_INSECURE_INTERNAL_HTTP=true`。该开关只接受 `kms-adapter`、`risk` 或
本机回环地址，且生产环境会拒绝启动。正式生产必须使用内部 HTTPS。

Create and apply a migration:

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

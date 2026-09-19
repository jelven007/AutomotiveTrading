# kms-adapter

面向内部服务的租户隔离 Secret Broker。每条 Secret 使用独立的 32 字节数据密钥
和 AES-256-GCM 加密，数据密钥由火山引擎 KMS 包装。

## 安全边界

- API 仅接受 `Authorization: Bearer <service-token>`。
- 加密上下文固定绑定 `tenant_id`、`secret_id` 和 `purpose`。
- 数据库仅保存业务密文、随机 Nonce、`CiphertextBlob` 和规范化上下文。
- 删除操作会清空所有恢复材料，删除后不可恢复。
- 明文数据密钥、API Key、私钥及云端错误详情均不写入数据库或 API 错误。

## 本地运行

本地进程仍需要可访问的火山引擎 KMS 和有效身份：

```bash
cp .env.example .env
uv sync --package kms-adapter --extra volcengine
uv run --package kms-adapter alembic upgrade head
uv run --package kms-adapter uvicorn kms_adapter.main:app --reload
```

生产环境至少配置：

```text
ENVIRONMENT=production
SERVICE_TOKEN=<至少 32 字节的随机令牌>
KMS_KEY_ID=<火山引擎 KMS 主密钥 ID>
KMS_REGION=cn-beijing
```

AK/SK/STS 只能通过进程环境或运行时身份注入，不得提交到仓库。使用临时身份时同时
设置 `VOLCENGINE_ACCESS_KEY`、`VOLCENGINE_SECRET_KEY` 和
`VOLCENGINE_SESSION_TOKEN`。

# Identity

提供邮箱密码注册与登录、JWT 会话、刷新令牌轮换和 TOTP MFA。

用户界面不要求用户 ID 或租户 ID。服务内部创建隔离空间并将其写入 JWT，供
Trading 执行授权。生产环境必须设置 `SINGLE_OWNER_MODE=true`：首位用户完成
初始化后关闭公开注册，并由数据库唯一记录保证并发注册不会产生第二位所有者。

本地启动：

```bash
export AUTH_JWT_SECRET="replace-with-at-least-32-random-bytes"
export AUTH_TOTP_ENCRYPTION_KEY="$(
  python -c \
    'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
)"
uv run uvicorn identity_tenant.main:create_app --factory --reload
```

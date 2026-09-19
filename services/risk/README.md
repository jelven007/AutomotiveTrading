# risk

确定性交易风控和短期审批令牌服务。

Run locally:

```bash
cp .env.example .env
uv run uvicorn risk.main:app --reload
```

调用方必须携带 `X-Service-Token`。生产环境必须通过 Secret 注入至少 32 字节的
`SERVICE_TOKEN`。

风险审批令牌默认 60 秒过期，仅能消费一次，并绑定租户、帐号和规范化订单指纹。
数据库不保存明文令牌。

Create and apply a migration:

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

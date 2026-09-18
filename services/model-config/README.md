# model-config

FastAPI microservice generated for the Quant Trading SaaS platform.

Run locally:

```bash
cp .env.example .env
uv run uvicorn model_config.main:app --reload
```

Set `AUTH_JWT_SECRET` to the identity service signing secret. Generate a local
secret encryption key with `Fernet.generate_key()`; production deployments must
replace the local backend with the KMS implementation.

Create and apply a migration:

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

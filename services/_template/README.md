# qt-service-template

FastAPI microservice generated for the Quant Trading SaaS platform.

Run locally:

```bash
uv run uvicorn service.main:app --reload
```

Create and apply a migration:

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

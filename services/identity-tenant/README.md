# identity-tenant

FastAPI microservice generated for the Quant Trading SaaS platform.

Run locally:

```bash
export AUTH_JWT_SECRET="replace-with-at-least-32-random-bytes"
export AUTH_TOTP_ENCRYPTION_KEY="$(
  python -c \
    'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
)"
uv run uvicorn identity_tenant.main:create_app --factory --reload
```

Create and apply a migration:

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

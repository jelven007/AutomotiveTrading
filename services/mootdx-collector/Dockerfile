FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /usr/local/bin/uv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_NO_CACHE=1
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable \
    && addgroup --system app && adduser --system --ingroup app --home /app app \
    && mkdir -p /data /app/.config && chown -R app:app /app /data
ENV PATH="/app/.venv/bin:$PATH" COLLECTOR_HEALTH_HOST=0.0.0.0
USER app
EXPOSE 8010
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/health/live', timeout=2)"]
CMD ["python", "-m", "mootdx_collector", "run"]

import base64
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_web_image_serves_spa_and_proxies_apis() -> None:
    dockerfile = read_text("apps/web/Dockerfile")
    nginx = read_text("apps/web/nginx.conf")

    assert "FROM node:22-alpine AS build" in dockerfile
    assert "pnpm --filter web build" in dockerfile
    assert "nginxinc/nginx-unprivileged" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "listen 8080" in nginx
    assert "try_files $uri $uri/ /index.html" in nginx
    assert "proxy_pass http://identity-tenant:8000" in nginx
    assert "proxy_pass http://model-config:8000" in nginx
    assert "resolver 127.0.0.11" in nginx
    assert "location ^~ /api/v1/market" in nginx
    assert "proxy_pass http://instrument-market:8000" in nginx
    assert "location ^~ /api/v1/trading" in nginx
    assert "trading:8000" in nginx


def test_deploy_compose_has_one_public_entrypoint() -> None:
    base_compose = read_text("infra/compose/docker-compose.yml")
    deploy_compose = read_text("infra/compose/docker-compose.deploy.yml")
    deploy_env = read_text("infra/compose/.env.deploy.example")

    assert "${QT_BIND_HOST:-0.0.0.0}" in base_compose
    assert "QT_BIND_HOST=127.0.0.1" in deploy_env
    assert "web:" in deploy_compose
    assert "0.0.0.0:${WEB_PORT:-80}:8080" in deploy_compose
    assert "${QT_BIND_HOST:-127.0.0.1}:${IDENTITY_PORT:-8001}:8000" in deploy_compose
    assert "${QT_BIND_HOST:-127.0.0.1}:${AUDIT_PORT:-8002}:8000" in deploy_compose
    assert "${QT_BIND_HOST:-127.0.0.1}:${MODEL_CONFIG_PORT:-8003}:8000" in deploy_compose
    assert "${QT_BIND_HOST:-127.0.0.1}:${INSTRUMENT_MARKET_PORT:-8007}:8000" in (deploy_compose)
    assert "clickhouse:" in base_compose
    assert "instrument-market:" in deploy_compose
    assert "instrument-market-migrate:" in deploy_compose
    assert 'profiles: ["binance-readonly"]' in deploy_compose
    for service in ("kms-adapter", "risk", "trading"):
        assert f"  {service}:" in deploy_compose
        assert f"  {service}-migrate:" in deploy_compose
    assert 'LIVE_TRADING_ENABLED: "false"' in deploy_compose
    assert 'ALLOW_INSECURE_INTERNAL_HTTP: "true"' in deploy_compose


def test_deploy_init_generates_valid_secrets(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.deploy"
    result = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "init"],
        cwd=ROOT,
        env={**os.environ, "QT_DEPLOY_ENV_FILE": str(env_file)},
        check=True,
        capture_output=True,
        text=True,
    )

    values = dict(
        line.split("=", 1)
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    assert "已生成部署配置" in result.stdout
    assert re.fullmatch(r"[a-f0-9]{48}", values["MYSQL_ROOT_PASSWORD"])
    assert re.fullmatch(r"[a-f0-9]{48}", values["MYSQL_PASSWORD"])
    assert re.fullmatch(r"[a-f0-9]{96}", values["AUTH_JWT_SECRET"])
    assert re.fullmatch(r"[a-f0-9]{96}", values["KMS_SERVICE_TOKEN"])
    assert re.fullmatch(r"[a-f0-9]{96}", values["RISK_SERVICE_TOKEN"])
    assert re.fullmatch(r"[a-f0-9]{48}", values["CLICKHOUSE_PASSWORD"])
    assert re.fullmatch(r"[a-f0-9]{96}", values["MARKET_INGEST_SERVICE_TOKEN"])
    assert values["KMS_SERVICE_TOKEN"] != values["RISK_SERVICE_TOKEN"]
    assert values["MARKET_INGEST_SERVICE_TOKEN"] not in {
        values["KMS_SERVICE_TOKEN"],
        values["RISK_SERVICE_TOKEN"],
    }
    assert values["FIXED_EGRESS_IP_CONFIGURED"] == "false"
    assert values["PUBLIC_BASE_URL"] == ""
    for name in ("AUTH_TOTP_ENCRYPTION_KEY", "SECRET_ENCRYPTION_KEY"):
        assert len(base64.urlsafe_b64decode(values[name])) == 32
    assert env_file.stat().st_mode & 0o777 == 0o600


def test_deploy_init_upgrades_existing_environment_without_overwrite(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env.deploy"
    env_file.write_text(
        "MYSQL_PASSWORD=existing-secret\nWEB_PORT=8088\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "init"],
        cwd=ROOT,
        env={**os.environ, "QT_DEPLOY_ENV_FILE": str(env_file)},
        check=True,
        capture_output=True,
        text=True,
    )
    values = dict(
        line.split("=", 1)
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )

    assert "已补全缺失字段" in result.stdout
    assert values["MYSQL_PASSWORD"] == "existing-secret"
    assert values["WEB_PORT"] == "8088"
    assert re.fullmatch(r"[a-f0-9]{48}", values["CLICKHOUSE_PASSWORD"])
    assert re.fullmatch(r"[a-f0-9]{96}", values["MARKET_INGEST_SERVICE_TOKEN"])
    assert env_file.stat().st_mode & 0o777 == 0o600


def test_deploy_rejects_placeholder_secrets(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.deploy"
    env_file.write_text("MYSQL_PASSWORD=please-change-app\n", encoding="utf-8")

    result = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "status"],
        cwd=ROOT,
        env={**os.environ, "QT_DEPLOY_ENV_FILE": str(env_file)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "仍包含 please-change" in result.stderr


def test_deploy_wait_ignores_successful_one_shot_containers() -> None:
    script = read_text("scripts/deploy.sh")

    assert "wait_for_jobs" in script
    assert "ExitCode" in script
    assert "wait_for_services" in script
    assert "readonly-databases-init" in script
    assert "kms-adapter-migrate" in script
    assert "risk-migrate" in script
    assert "trading-migrate" in script
    assert "instrument-market-migrate" in script
    assert "instrument-market" in script
    assert "clickhouse" in script
    assert "compose_cmd up -d --build --remove-orphans --wait" not in script


def test_readonly_deploy_requires_external_configuration(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.deploy"
    init_result = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "init"],
        cwd=ROOT,
        env={**os.environ, "QT_DEPLOY_ENV_FILE": str(env_file)},
        check=True,
        capture_output=True,
        text=True,
    )
    assert init_result.returncode == 0

    result = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "readonly-up"],
        cwd=ROOT,
        env={**os.environ, "QT_DEPLOY_ENV_FILE": str(env_file)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "KMS_KEY_ID" in result.stderr


def test_readonly_deploy_requires_public_https(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.deploy"
    subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "init"],
        cwd=ROOT,
        env={**os.environ, "QT_DEPLOY_ENV_FILE": str(env_file)},
        check=True,
        capture_output=True,
        text=True,
    )
    configured = (
        env_file.read_text(encoding="utf-8")
        .replace("KMS_KEY_ID=", "KMS_KEY_ID=test-key")
        .replace("VOLCENGINE_ACCESS_KEY=", "VOLCENGINE_ACCESS_KEY=test-ak")
        .replace("VOLCENGINE_SECRET_KEY=", "VOLCENGINE_SECRET_KEY=test-sk")
        .replace("FIXED_EGRESS_IP_CONFIGURED=false", "FIXED_EGRESS_IP_CONFIGURED=true")
    )
    env_file.write_text(configured, encoding="utf-8")

    result = subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), "readonly-up"],
        cwd=ROOT,
        env={**os.environ, "QT_DEPLOY_ENV_FILE": str(env_file)},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "PUBLIC_BASE_URL" in result.stderr


def test_readonly_database_bootstrap_is_present() -> None:
    init_sql = read_text("infra/compose/mysql/init.sql")
    ensure_script = read_text("infra/compose/mysql/ensure-readonly-databases.sh")

    assert "CREATE DATABASE IF NOT EXISTS qt_kms" in init_sql
    assert "CREATE DATABASE IF NOT EXISTS qt_kms" in ensure_script
    assert "GRANT ALL PRIVILEGES ON qt_kms.*" in ensure_script


def test_kafka_topic_bootstrap_is_idempotent() -> None:
    script = read_text("infra/compose/kafka/create-topics.sh")

    assert 'rpk topic describe "$topic"' in script
    assert "market.raw.received.v1" in script
    assert "market.quote.updated.v1" in script

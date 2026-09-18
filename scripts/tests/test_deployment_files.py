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
    for name in ("AUTH_TOTP_ENCRYPTION_KEY", "SECRET_ENCRYPTION_KEY"):
        assert len(base64.urlsafe_b64decode(values[name])) == 32
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
    assert "compose_cmd up -d --build --remove-orphans --wait" not in script


def test_kafka_topic_bootstrap_is_idempotent() -> None:
    script = read_text("infra/compose/kafka/create-topics.sh")

    assert 'rpk topic describe "$topic"' in script

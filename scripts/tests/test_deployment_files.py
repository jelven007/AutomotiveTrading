import base64
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def read_text(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def run_deploy(env_file: Path, command: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(ROOT / "scripts/deploy.sh"), command],
        cwd=ROOT,
        env={**os.environ, "QT_DEPLOY_ENV_FILE": str(env_file)},
        capture_output=True,
        text=True,
    )


def init_env(env_file: Path) -> dict[str, str]:
    result = run_deploy(env_file, "init")
    assert result.returncode == 0
    return dict(
        line.split("=", 1)
        for line in env_file.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )


def append_env(env_file: Path, **values: str) -> None:
    with env_file.open("a", encoding="utf-8") as stream:
        for key, value in values.items():
            stream.write(f"{key}={value}\n")


def valid_key(tmp_path: Path) -> Path:
    path = tmp_path / "credential-master-key"
    path.write_bytes(b"k" * 32)
    path.chmod(0o600)
    return path


def test_web_only_proxies_identity_and_trading() -> None:
    nginx = read_text("apps/web/nginx.conf")

    assert "proxy_pass http://identity-tenant:8000" in nginx
    assert "set $trading_upstream trading:8000" in nginx
    assert "model-config" not in nginx
    assert "instrument-market" not in nginx


def test_compose_contains_only_minimal_services() -> None:
    compose = yaml.safe_load(read_text("infra/compose/docker-compose.yml"))

    assert set(compose["services"]) == {
        "mysql",
        "database-init",
        "identity-migrate",
        "identity-tenant",
        "trading-migrate",
        "trading",
        "web",
    }
    assert set(compose["volumes"]) == {"mysql-data"}
    assert compose["services"]["trading"]["environment"]["LIVE_TRADING_ENABLED"] == (
        "${LIVE_TRADING_ENABLED:-false}"
    )
    for service in ("trading-migrate", "trading"):
        mount = compose["services"][service]["volumes"][0]
        assert mount.endswith(":/opt/quant-trading/secrets/credential-master-key:ro")


def test_deploy_init_generates_minimal_secure_environment(tmp_path: Path) -> None:
    env_file = tmp_path / ".env.deploy"
    values = init_env(env_file)

    assert set(values) == {
        "MYSQL_ROOT_PASSWORD",
        "MYSQL_USER",
        "MYSQL_PASSWORD",
        "AUTH_JWT_SECRET",
        "AUTH_TOTP_ENCRYPTION_KEY",
        "ENVIRONMENT",
        "QT_BIND_HOST",
        "MYSQL_PORT",
        "IDENTITY_PORT",
        "TRADING_PORT",
        "WEB_BIND_HOST",
        "WEB_PORT",
        "BINANCE_CREDENTIAL_MASTER_KEY_FILE",
        "BINANCE_CREDENTIAL_MASTER_KEY_UID",
        "BINANCE_TESTNET_ENABLED",
        "FIXED_EGRESS_IP_CONFIGURED",
        "LIVE_TRADING_ENABLED",
        "PUBLIC_BASE_URL",
    }
    assert re.fullmatch(r"[a-f0-9]{48}", values["MYSQL_ROOT_PASSWORD"])
    assert re.fullmatch(r"[a-f0-9]{48}", values["MYSQL_PASSWORD"])
    assert re.fullmatch(r"[a-f0-9]{96}", values["AUTH_JWT_SECRET"])
    assert len(base64.urlsafe_b64decode(values["AUTH_TOTP_ENCRYPTION_KEY"])) == 32
    assert values["LIVE_TRADING_ENABLED"] == "false"
    assert env_file.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    ("prepare", "expected"),
    [
        ("missing", "不存在"),
        ("mode", "600"),
        ("owner", "Trading UID"),
        ("egress", "FIXED_EGRESS_IP_CONFIGURED"),
        ("live", "LIVE_TRADING_ENABLED=false"),
        ("https", "PUBLIC_BASE_URL"),
    ],
)
def test_deploy_rejects_unsafe_binance_configuration(
    tmp_path: Path,
    prepare: str,
    expected: str,
) -> None:
    env_file = tmp_path / ".env.deploy"
    init_env(env_file)
    key_file = valid_key(tmp_path)
    values = {
        "BINANCE_CREDENTIAL_MASTER_KEY_FILE": str(key_file),
        "BINANCE_CREDENTIAL_MASTER_KEY_UID": str(os.getuid()),
        "FIXED_EGRESS_IP_CONFIGURED": "true",
        "LIVE_TRADING_ENABLED": "false",
        "PUBLIC_BASE_URL": "https://example.test",
    }
    if prepare == "missing":
        values["BINANCE_CREDENTIAL_MASTER_KEY_FILE"] = str(tmp_path / "missing")
    elif prepare == "mode":
        key_file.chmod(0o644)
    elif prepare == "owner":
        values["BINANCE_CREDENTIAL_MASTER_KEY_UID"] = str(os.getuid() + 1)
    elif prepare == "egress":
        values["FIXED_EGRESS_IP_CONFIGURED"] = "false"
    elif prepare == "live":
        values["LIVE_TRADING_ENABLED"] = "true"
    elif prepare == "https":
        values["PUBLIC_BASE_URL"] = "http://example.test"
    append_env(env_file, **values)

    result = run_deploy(env_file, "up")

    assert result.returncode == 1
    assert expected in result.stderr


def test_database_bootstrap_only_creates_identity_and_trading() -> None:
    script = read_text("infra/compose/mysql/ensure-databases.sh")
    init_sql = read_text("infra/compose/mysql/init.sql")

    for content in (script, init_sql):
        assert "qt_identity" in content
        assert "qt_trading" in content
        assert "qt_market" not in content
        assert "qt_kms" not in content
        assert "qt_risk" not in content


def test_deploy_script_only_manages_minimal_services() -> None:
    script = read_text("scripts/deploy.sh")

    assert "database-init identity-migrate trading-migrate" in script
    assert "mysql identity-tenant trading web" in script
    for removed in ("kafka", "redis", "minio", "mootdx", "model-config", "risk"):
        assert removed not in script.lower()

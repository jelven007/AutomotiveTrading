from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
COMPOSE_ROOT = ROOT / "infra" / "compose"


def load_compose(name: str) -> dict[str, object]:
    return yaml.safe_load((COMPOSE_ROOT / name).read_text())


def test_base_compose_defines_persistent_clickhouse() -> None:
    compose = load_compose("docker-compose.yml")
    services = compose["services"]
    volumes = compose["volumes"]
    clickhouse = services["clickhouse"]

    assert clickhouse["image"] == "clickhouse/clickhouse-server:25.8-alpine"
    assert clickhouse["healthcheck"]["test"]
    assert "clickhouse-data:/var/lib/clickhouse" in clickhouse["volumes"]
    assert "clickhouse-data" in volumes
    assert "clickhouse-logs" in volumes


def test_deploy_compose_wires_instrument_market_to_dependencies() -> None:
    compose = load_compose("docker-compose.deploy.yml")
    service = compose["services"]["instrument-market"]

    assert service["environment"]["CLICKHOUSE_URL"] == "http://clickhouse:8123"
    assert service["environment"]["REDIS_URL"] == "redis://redis:6379/0"
    assert service["environment"]["KAFKA_BOOTSTRAP_SERVERS"] == "kafka:29092"
    assert service["depends_on"]["clickhouse"]["condition"] == "service_healthy"
    assert service["depends_on"]["instrument-market-migrate"]["condition"] == (
        "service_completed_successfully"
    )


def test_mysql_initialization_contains_market_database() -> None:
    init_sql = (COMPOSE_ROOT / "mysql" / "init.sql").read_text()

    assert "CREATE DATABASE IF NOT EXISTS qt_market" in init_sql
    assert "GRANT ALL PRIVILEGES ON qt_market.*" in init_sql

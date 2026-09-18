from __future__ import annotations

import os
import socket
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).parents[2] / "infra" / "compose" / ".env")


def service_port(name: str, default: int) -> int:
    return int(os.getenv(f"QT_{name.upper().replace(' ', '_')}_PORT", str(default)))


def tcp_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def http_healthy(url: str, timeout: float = 1.0) -> bool:
    try:
        with urlopen(url, timeout=timeout) as response:
            return 200 <= response.status < 300
    except URLError:
        return False


@pytest.mark.parametrize(
    ("service", "port"),
    [
        ("MySQL", service_port("MySQL", 3306)),
        ("Redis", service_port("Redis", 6379)),
        ("Kafka", service_port("Kafka", 9092)),
        ("Schema Registry", service_port("Schema Registry", 8081)),
        ("Mailpit", service_port("Mailpit", 8025)),
    ],
)
def test_service_port_is_reachable(service: str, port: int) -> None:
    assert tcp_open("127.0.0.1", port), f"{service} is not reachable on port {port}"


def test_minio_is_healthy() -> None:
    port = service_port("MinIO", 9000)
    assert http_healthy(f"http://127.0.0.1:{port}/minio/health/live")

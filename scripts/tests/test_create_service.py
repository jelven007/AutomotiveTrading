import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CREATE_SERVICE = PROJECT_ROOT / "scripts" / "create_service.py"


def test_create_service_generates_runnable_service(tmp_path: Path) -> None:
    output_root = tmp_path / "services"

    result = subprocess.run(
        [
            sys.executable,
            str(CREATE_SERVICE),
            "sample-service",
            "--output-root",
            str(output_root),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr

    service_root = output_root / "sample-service"
    expected_files = [
        "Dockerfile",
        "alembic.ini",
        "migrations/env.py",
        "pyproject.toml",
        "src/service/api/health.py",
        "src/service/config.py",
        "src/service/db.py",
        "src/service/main.py",
        "tests/test_health.py",
    ]
    assert all((service_root / path).is_file() for path in expected_files)

    pyproject = (service_root / "pyproject.toml").read_text()
    assert 'name = "sample-service"' in pyproject
    assert "qt-service-template" not in pyproject

    config = (service_root / "src/service/config.py").read_text()
    assert 'default="sample-service"' in config

    health = (service_root / "src/service/api/health.py").read_text()
    assert '"/health/live"' in health
    assert '"/health/ready"' in health

    dockerfile = (service_root / "Dockerfile").read_text()
    assert "HEALTHCHECK" in dockerfile


def test_create_service_rejects_invalid_name(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(CREATE_SERVICE),
            "Sample_Service",
            "--output-root",
            str(tmp_path),
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode != 0
    assert "kebab-case" in result.stderr

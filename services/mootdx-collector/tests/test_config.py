import pytest
from mootdx_collector.config import Settings


@pytest.mark.parametrize(
    "values",
    [
        {"workers": 17},
        {"workers": 0},
        {"batch_size": 81},
        {"timeout": 0},
        {"max_pending": 0},
        {"core_url": "ftp://localhost"},
        {"core_url": "http://user:password@localhost"},
    ],
)
def test_settings_reject_unsafe_bounds(values):
    with pytest.raises(ValueError):
        Settings(**values)


def test_settings_env_and_secret_redaction(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INGEST_SERVICE_TOKEN", "secret-test")
    monkeypatch.setenv("COLLECTOR_SPOOL_PATH", str(tmp_path / "spool.db"))
    monkeypatch.setenv("COLLECTOR_WORKERS", "3")
    settings = Settings.from_env()
    assert settings.workers == 3
    assert settings.spool_path == tmp_path / "spool.db"
    assert settings.service_token == "secret-test"
    assert "secret-test" not in repr(settings)

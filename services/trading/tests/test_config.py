import os
import stat

import pytest
from pydantic import ValidationError
from trading.config import Settings
from trading.secrets import LocalCredentialVault


def test_production_accepts_local_master_key_configuration() -> None:
    settings = Settings(
        environment="production",
        auth_jwt_secret="test-signing-secret-that-is-at-least-32-bytes",
        binance_credential_master_key_file="/opt/quant-trading/secrets/credential-master-key",
    )

    assert settings.environment == "production"


def test_master_key_requires_32_bytes() -> None:
    with pytest.raises(ValueError, match="exactly 32"):
        LocalCredentialVault(b"short")


def test_master_key_file_rejects_group_permissions(tmp_path) -> None:
    key_file = tmp_path / "credential-master-key"
    key_file.write_bytes(b"k" * 32)
    os.chmod(key_file, stat.S_IRUSR | stat.S_IRGRP)

    with pytest.raises(PermissionError, match="owner"):
        LocalCredentialVault.from_file(str(key_file))


def test_settings_still_validates_authentication_secret() -> None:
    with pytest.raises(ValidationError, match="authentication signing secret"):
        Settings(environment="production", auth_jwt_secret=None)

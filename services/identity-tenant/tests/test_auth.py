from datetime import UTC, datetime

import jwt
import pyotp
import pytest
from identity_tenant.auth import (
    AuthenticationError,
    AuthService,
    MfaRequiredError,
    RefreshTokenReuseError,
    require_recent_mfa,
)
from identity_tenant.models import AuthSession, Role, User
from sqlalchemy import select
from sqlalchemy.orm import Session


def test_registration_and_login_issue_oidc_compatible_token(
    auth_service: AuthService,
    session: Session,
) -> None:
    registration = auth_service.register(
        email="owner@example.com",
        display_name="Owner",
        password="Correct-Horse-Battery-99",
        tenant_name="Alpha Capital",
    )

    user = session.scalar(select(User).where(User.email == "owner@example.com"))
    assert user is not None
    assert user.password_hash.startswith("$argon2id$")
    assert "Correct-Horse-Battery-99" not in user.password_hash

    token_pair = auth_service.login(
        email="OWNER@example.com",
        password="Correct-Horse-Battery-99",
        tenant_id=registration.tenant_id,
    )
    claims = jwt.decode(
        token_pair.access_token,
        auth_service.settings.jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        audience=auth_service.settings.audience,
        issuer=auth_service.settings.issuer,
    )

    assert claims["sub"] == registration.user_id
    assert claims["tenant_id"] == registration.tenant_id
    assert claims["roles"] == [Role.TENANT_ADMIN.value]
    assert claims["typ"] == "access"
    assert claims["sid"]
    assert claims["jti"]
    assert claims["exp"] > claims["iat"]
    assert claims["mfa_enabled"] is False


def test_refresh_token_rotates_and_replay_revokes_session_family(
    auth_service: AuthService,
) -> None:
    registration = auth_service.register(
        email="trader@example.com",
        display_name="Trader",
        password="Correct-Horse-Battery-99",
        tenant_name="Alpha Capital",
    )
    first = auth_service.login(
        email="trader@example.com",
        password="Correct-Horse-Battery-99",
        tenant_id=registration.tenant_id,
    )

    second = auth_service.refresh(first.refresh_token)
    assert second.refresh_token != first.refresh_token

    with pytest.raises(RefreshTokenReuseError):
        auth_service.refresh(first.refresh_token)

    with pytest.raises(AuthenticationError):
        auth_service.authenticate_access_token(second.access_token)


def test_logout_revokes_access_and_refresh_tokens(auth_service: AuthService) -> None:
    registration = auth_service.register(
        email="auditor@example.com",
        display_name="Auditor",
        password="Correct-Horse-Battery-99",
        tenant_name="Alpha Capital",
    )
    tokens = auth_service.login(
        email="auditor@example.com",
        password="Correct-Horse-Battery-99",
        tenant_id=registration.tenant_id,
    )

    auth_service.logout(tokens.access_token)

    with pytest.raises(AuthenticationError):
        auth_service.authenticate_access_token(tokens.access_token)
    with pytest.raises(AuthenticationError):
        auth_service.refresh(tokens.refresh_token)


def test_totp_secret_is_encrypted_and_mfa_timestamp_is_recorded(
    auth_service: AuthService,
    session: Session,
) -> None:
    registration = auth_service.register(
        email="admin@example.com",
        display_name="Admin",
        password="Correct-Horse-Battery-99",
        tenant_name="Alpha Capital",
    )
    enrollment = auth_service.begin_totp_enrollment(registration.user_id)

    user = session.get(User, registration.user_id)
    assert user is not None
    assert user.totp_secret_encrypted is not None
    assert enrollment.secret not in user.totp_secret_encrypted
    assert enrollment.provisioning_uri.startswith("otpauth://totp/")

    auth_service.confirm_totp_enrollment(
        registration.user_id,
        pyotp.TOTP(enrollment.secret).now(),
    )

    assert user.mfa_enabled is True
    assert user.mfa_confirmed_at is not None
    assert user.mfa_confirmed_at <= datetime.now(UTC).replace(tzinfo=None)
    with pytest.raises(AuthenticationError, match="already configured"):
        auth_service.begin_totp_enrollment(registration.user_id)


def test_totp_verification_marks_session_for_high_risk_operations(
    auth_service: AuthService,
) -> None:
    registration = auth_service.register(
        email="trader@example.com",
        display_name="Trader",
        password="Correct-Horse-Battery-99",
        tenant_name="Alpha Capital",
    )
    tokens = auth_service.login(
        email="trader@example.com",
        password="Correct-Horse-Battery-99",
        tenant_id=registration.tenant_id,
    )
    enrollment = auth_service.begin_totp_enrollment(registration.user_id)

    with pytest.raises(MfaRequiredError):
        require_recent_mfa(auth_service.authenticate_access_token(tokens.access_token))

    elevated_token = auth_service.verify_totp(
        tokens.access_token,
        pyotp.TOTP(enrollment.secret).now(),
    )
    principal = auth_service.authenticate_access_token(elevated_token)

    require_recent_mfa(principal)
    claims = jwt.decode(
        elevated_token,
        auth_service.settings.jwt_secret.get_secret_value(),
        algorithms=["HS256"],
        audience=auth_service.settings.audience,
        issuer=auth_service.settings.issuer,
    )
    assert claims["amr"] == ["pwd", "otp"]
    assert claims["mfa_enabled"] is True
    assert claims["mfa_time"] <= int(datetime.now(UTC).timestamp())
    assert claims["mfa_time"] > claims["iat"] - 2


def test_wrong_password_is_rejected(auth_service: AuthService) -> None:
    registration = auth_service.register(
        email="owner@example.com",
        display_name="Owner",
        password="Correct-Horse-Battery-99",
        tenant_name="Alpha Capital",
    )

    with pytest.raises(AuthenticationError):
        auth_service.login(
            email="owner@example.com",
            password="wrong-password",
            tenant_id=registration.tenant_id,
        )


def test_refresh_tokens_are_never_stored_in_plaintext(
    auth_service: AuthService,
    session: Session,
) -> None:
    registration = auth_service.register(
        email="owner@example.com",
        display_name="Owner",
        password="Correct-Horse-Battery-99",
        tenant_name="Alpha Capital",
    )
    tokens = auth_service.login(
        email="owner@example.com",
        password="Correct-Horse-Battery-99",
        tenant_id=registration.tenant_id,
    )

    stored_session = session.scalar(select(AuthSession))
    assert stored_session is not None
    assert stored_session.refresh_token_hash != tokens.refresh_token
    assert len(stored_session.refresh_token_hash) == 64

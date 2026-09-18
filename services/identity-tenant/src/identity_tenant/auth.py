import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet
from cryptography.fernet import InvalidToken as InvalidEncryptedToken
from jwt import InvalidTokenError
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from identity_tenant.models import AuthSession, Role, Tenant, TenantMember, User, new_id
from identity_tenant.rbac import AuthorizationError, Permission, require_permission


class AuthSettings(BaseModel):
    issuer: str = "https://identity.quant-trading.local"
    audience: str = "quant-api"
    jwt_secret: SecretStr = Field(min_length=32)
    totp_encryption_key: SecretStr
    access_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    refresh_token_ttl_seconds: int = Field(default=2_592_000, ge=300)


@dataclass(frozen=True)
class Registration:
    user_id: str
    tenant_id: str


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    session_id: str
    roles: tuple[Role, ...]
    mfa_verified_at: datetime | None


@dataclass(frozen=True)
class TotpEnrollment:
    secret: str
    provisioning_uri: str


class AuthenticationError(Exception):
    pass


class RefreshTokenReuseError(AuthenticationError):
    pass


class MfaRequiredError(AuthenticationError):
    pass


class RegistrationError(Exception):
    pass


def require_recent_mfa(principal: Principal, max_age_seconds: int = 300) -> None:
    if principal.mfa_verified_at is None:
        raise MfaRequiredError("recent MFA verification is required")
    age = datetime.now(UTC).replace(tzinfo=None) - principal.mfa_verified_at
    if age > timedelta(seconds=max_age_seconds):
        raise MfaRequiredError("recent MFA verification is required")


class AuthService:
    def __init__(self, session: Session, settings: AuthSettings) -> None:
        self.session = session
        self.settings = settings
        self.password_hasher = PasswordHasher()
        self.totp_cipher = Fernet(settings.totp_encryption_key.get_secret_value().encode())

    def register(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
        tenant_name: str,
    ) -> Registration:
        normalized_email = email.strip().lower()
        if len(password) < 12:
            raise RegistrationError("password must contain at least 12 characters")
        if self.session.scalar(select(User.id).where(User.email == normalized_email)):
            raise RegistrationError("email is already registered")

        user = User(
            email=normalized_email,
            display_name=display_name.strip(),
            password_hash=self.password_hasher.hash(password),
        )
        tenant = Tenant(name=tenant_name.strip())
        self.session.add_all([user, tenant])
        self.session.flush()
        self.session.add(
            TenantMember(
                tenant_id=tenant.id,
                user_id=user.id,
                role=Role.TENANT_ADMIN,
            )
        )
        self.session.commit()
        return Registration(user_id=user.id, tenant_id=tenant.id)

    def create_tenant(self, name: str) -> Tenant:
        tenant = Tenant(name=name.strip())
        self.session.add(tenant)
        self.session.commit()
        return tenant

    def add_member(
        self,
        *,
        actor_user_id: str,
        actor_tenant_id: str,
        tenant_id: str,
        user_id: str,
        role: Role,
    ) -> TenantMember:
        actor_roles = self._roles_for_user(actor_user_id, actor_tenant_id)
        require_permission(actor_roles, Permission.MEMBER_MANAGE)
        if actor_tenant_id != tenant_id:
            raise AuthorizationError("cannot manage members of another tenant")

        member = TenantMember(tenant_id=tenant_id, user_id=user_id, role=role)
        self.session.add(member)
        self.session.commit()
        return member

    def login(self, *, email: str, password: str, tenant_id: str) -> TokenPair:
        user = self.session.scalar(select(User).where(User.email == email.strip().lower()))
        if user is None or user.status != "active":
            raise AuthenticationError("invalid credentials")
        try:
            self.password_hasher.verify(user.password_hash, password)
        except (InvalidHashError, VerificationError) as error:
            raise AuthenticationError("invalid credentials") from error

        roles = self._roles_for_user(user.id, tenant_id)
        if not roles:
            raise AuthenticationError("tenant membership is not active")
        return self._create_session(user.id, tenant_id, roles)

    def refresh(self, refresh_token: str) -> TokenPair:
        token_hash = self._hash_refresh_token(refresh_token)
        old_session = self.session.scalar(
            select(AuthSession).where(AuthSession.refresh_token_hash == token_hash)
        )
        if old_session is None:
            raise AuthenticationError("invalid refresh token")
        if old_session.replaced_by_session_id is not None:
            self._revoke_session_family(old_session.family_id)
            raise RefreshTokenReuseError("refresh token reuse detected")
        if old_session.revoked_at is not None or old_session.expires_at <= self._now():
            raise AuthenticationError("refresh token is inactive")

        roles = self._roles_for_user(old_session.user_id, old_session.tenant_id)
        if not roles:
            self._revoke_session_family(old_session.family_id)
            raise AuthenticationError("tenant membership is not active")

        replacement = self._new_session(
            user_id=old_session.user_id,
            tenant_id=old_session.tenant_id,
            family_id=old_session.family_id,
            mfa_verified_at=old_session.mfa_verified_at,
        )
        old_session.revoked_at = self._now()
        old_session.replaced_by_session_id = replacement[0].id
        self.session.commit()
        return self._token_pair(replacement[0], replacement[1], roles)

    def logout(self, access_token: str) -> None:
        principal = self.authenticate_access_token(access_token)
        auth_session = self.session.get(AuthSession, principal.session_id)
        if auth_session is None:
            raise AuthenticationError("session is inactive")
        self._revoke_session_family(auth_session.family_id)

    def authenticate_access_token(self, access_token: str) -> Principal:
        try:
            claims = jwt.decode(
                access_token,
                self.settings.jwt_secret.get_secret_value(),
                algorithms=["HS256"],
                audience=self.settings.audience,
                issuer=self.settings.issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "jti", "sid"]},
            )
        except InvalidTokenError as error:
            raise AuthenticationError("invalid access token") from error

        if claims.get("typ") != "access":
            raise AuthenticationError("invalid token type")
        auth_session = self.session.get(AuthSession, claims["sid"])
        if auth_session is None or auth_session.revoked_at is not None:
            raise AuthenticationError("session is inactive")
        if auth_session.user_id != claims["sub"] or auth_session.tenant_id != claims["tenant_id"]:
            raise AuthenticationError("token session mismatch")

        roles = self._roles_for_user(auth_session.user_id, auth_session.tenant_id)
        if not roles:
            raise AuthenticationError("tenant membership is not active")
        return Principal(
            user_id=auth_session.user_id,
            tenant_id=auth_session.tenant_id,
            session_id=auth_session.id,
            roles=tuple(roles),
            mfa_verified_at=auth_session.mfa_verified_at,
        )

    def begin_totp_enrollment(self, user_id: str) -> TotpEnrollment:
        user = self.session.get(User, user_id)
        if user is None:
            raise AuthenticationError("user not found")
        secret = pyotp.random_base32()
        user.totp_secret_encrypted = self.totp_cipher.encrypt(secret.encode()).decode()
        user.mfa_enabled = False
        self.session.commit()
        uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="Quant Desk")
        return TotpEnrollment(secret=secret, provisioning_uri=uri)

    def confirm_totp_enrollment(self, user_id: str, code: str) -> None:
        user = self.session.get(User, user_id)
        if user is None or user.totp_secret_encrypted is None:
            raise AuthenticationError("TOTP enrollment has not started")
        try:
            secret = self.totp_cipher.decrypt(user.totp_secret_encrypted.encode()).decode()
        except InvalidEncryptedToken as error:
            raise AuthenticationError("TOTP secret is invalid") from error
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise AuthenticationError("invalid TOTP code")
        user.mfa_enabled = True
        user.mfa_confirmed_at = self._now()
        self.session.commit()

    def verify_totp(self, access_token: str, code: str) -> str:
        principal = self.authenticate_access_token(access_token)
        user = self.session.get(User, principal.user_id)
        auth_session = self.session.get(AuthSession, principal.session_id)
        if user is None or user.totp_secret_encrypted is None or auth_session is None:
            raise AuthenticationError("TOTP enrollment has not started")
        try:
            secret = self.totp_cipher.decrypt(user.totp_secret_encrypted.encode()).decode()
        except InvalidEncryptedToken as error:
            raise AuthenticationError("TOTP secret is invalid") from error
        if not pyotp.TOTP(secret).verify(code, valid_window=1):
            raise AuthenticationError("invalid TOTP code")

        verified_at = self._now()
        user.mfa_enabled = True
        user.mfa_confirmed_at = user.mfa_confirmed_at or verified_at
        auth_session.mfa_verified_at = verified_at
        self.session.commit()
        roles = self._roles_for_user(principal.user_id, principal.tenant_id)
        return self._encode_access_token(auth_session, roles)

    def _create_session(self, user_id: str, tenant_id: str, roles: list[Role]) -> TokenPair:
        auth_session, refresh_token = self._new_session(
            user_id=user_id,
            tenant_id=tenant_id,
            family_id=new_id(),
        )
        self.session.commit()
        return self._token_pair(auth_session, refresh_token, roles)

    def _new_session(
        self,
        *,
        user_id: str,
        tenant_id: str,
        family_id: str,
        mfa_verified_at: datetime | None = None,
    ) -> tuple[AuthSession, str]:
        refresh_token = secrets.token_urlsafe(48)
        auth_session = AuthSession(
            family_id=family_id,
            user_id=user_id,
            tenant_id=tenant_id,
            refresh_token_hash=self._hash_refresh_token(refresh_token),
            expires_at=self._now() + timedelta(seconds=self.settings.refresh_token_ttl_seconds),
            mfa_verified_at=mfa_verified_at,
        )
        self.session.add(auth_session)
        self.session.flush()
        return auth_session, refresh_token

    def _token_pair(
        self,
        auth_session: AuthSession,
        refresh_token: str,
        roles: list[Role],
    ) -> TokenPair:
        return TokenPair(
            access_token=self._encode_access_token(auth_session, roles),
            refresh_token=refresh_token,
            expires_in=self.settings.access_token_ttl_seconds,
        )

    def _encode_access_token(
        self,
        auth_session: AuthSession,
        roles: list[Role],
    ) -> str:
        now = datetime.now(UTC)
        claims = {
            "iss": self.settings.issuer,
            "aud": self.settings.audience,
            "sub": auth_session.user_id,
            "tenant_id": auth_session.tenant_id,
            "roles": [role.value for role in roles],
            "scope": " ".join(
                sorted(
                    {
                        permission.value
                        for role in roles
                        for permission in self._permissions_for_role(role)
                    }
                )
            ),
            "sid": auth_session.id,
            "jti": new_id(),
            "typ": "access",
            "iat": now,
            "exp": now + timedelta(seconds=self.settings.access_token_ttl_seconds),
            "auth_time": int(auth_session.created_at.replace(tzinfo=UTC).timestamp()),
            "amr": ["pwd"] + (["otp"] if auth_session.mfa_verified_at else []),
        }
        return jwt.encode(
            claims,
            self.settings.jwt_secret.get_secret_value(),
            algorithm="HS256",
        )

    def _roles_for_user(self, user_id: str, tenant_id: str) -> list[Role]:
        return list(
            self.session.scalars(
                select(TenantMember.role).where(
                    TenantMember.user_id == user_id,
                    TenantMember.tenant_id == tenant_id,
                    TenantMember.status == "active",
                )
            )
        )

    @staticmethod
    def _permissions_for_role(role: Role) -> frozenset[Permission]:
        from identity_tenant.rbac import ROLE_PERMISSIONS

        return ROLE_PERMISSIONS[role]

    def _revoke_session_family(self, family_id: str) -> None:
        self.session.execute(
            update(AuthSession)
            .where(AuthSession.family_id == family_id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=self._now())
        )
        self.session.commit()

    @staticmethod
    def _hash_refresh_token(refresh_token: str) -> str:
        return hashlib.sha256(refresh_token.encode()).hexdigest()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

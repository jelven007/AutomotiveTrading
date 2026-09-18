from enum import StrEnum

from identity_tenant.models import Role


class Permission(StrEnum):
    PLATFORM_ADMIN = "platform.admin"
    MEMBER_MANAGE = "tenant.members.manage"
    # Authorization permission identifier, not a credential.
    SECRET_MANAGE = "tenant.secrets.manage"  # nosec B105
    STRATEGY_READ = "strategy.read"
    STRATEGY_WRITE = "strategy.write"
    TRADE_READ = "trade.read"
    TRADE_WRITE = "trade.write"
    AUDIT_READ = "audit.read"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.PLATFORM_ADMIN: frozenset({Permission.PLATFORM_ADMIN}),
    Role.TENANT_ADMIN: frozenset(
        {
            Permission.MEMBER_MANAGE,
            Permission.SECRET_MANAGE,
            Permission.STRATEGY_READ,
            Permission.STRATEGY_WRITE,
            Permission.TRADE_READ,
            Permission.TRADE_WRITE,
            Permission.AUDIT_READ,
        }
    ),
    Role.RESEARCHER: frozenset(
        {
            Permission.STRATEGY_READ,
            Permission.STRATEGY_WRITE,
        }
    ),
    Role.TRADER: frozenset(
        {
            Permission.STRATEGY_READ,
            Permission.TRADE_READ,
            Permission.TRADE_WRITE,
        }
    ),
    Role.AUDITOR: frozenset(
        {
            Permission.STRATEGY_READ,
            Permission.TRADE_READ,
            Permission.AUDIT_READ,
        }
    ),
}


class AuthorizationError(Exception):
    pass


def require_permission(roles: list[Role] | tuple[Role, ...], permission: Permission) -> None:
    if not any(permission in ROLE_PERMISSIONS[role] for role in roles):
        raise AuthorizationError(f"missing permission: {permission}")

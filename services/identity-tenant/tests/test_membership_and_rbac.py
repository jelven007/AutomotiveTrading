import pytest
from identity_tenant.auth import AuthService
from identity_tenant.models import Role, TenantMember
from identity_tenant.rbac import AuthorizationError, Permission, require_permission
from sqlalchemy import select
from sqlalchemy.orm import Session


@pytest.mark.parametrize(
    ("role", "allowed", "denied"),
    [
        (Role.PLATFORM_ADMIN, Permission.PLATFORM_ADMIN, Permission.TRADE_WRITE),
        (Role.TENANT_ADMIN, Permission.MEMBER_MANAGE, Permission.PLATFORM_ADMIN),
        (Role.RESEARCHER, Permission.STRATEGY_WRITE, Permission.TRADE_WRITE),
        (Role.TRADER, Permission.TRADE_WRITE, Permission.SECRET_MANAGE),
        (Role.AUDITOR, Permission.AUDIT_READ, Permission.STRATEGY_WRITE),
    ],
)
def test_five_roles_enforce_permissions(
    role: Role,
    allowed: Permission,
    denied: Permission,
) -> None:
    require_permission([role], allowed)

    with pytest.raises(AuthorizationError):
        require_permission([role], denied)


def test_user_can_join_multiple_tenants_with_distinct_roles(
    auth_service: AuthService,
    session: Session,
) -> None:
    owner = auth_service.register(
        email="owner@example.com",
        display_name="Owner",
        password="Correct-Horse-Battery-99",
        tenant_name="Alpha Capital",
    )
    second_tenant = auth_service.create_tenant("Beta Capital")

    session.add(
        TenantMember(
            tenant_id=second_tenant.id,
            user_id=owner.user_id,
            role=Role.AUDITOR,
        )
    )
    session.commit()

    memberships = session.scalars(
        select(TenantMember).where(TenantMember.user_id == owner.user_id)
    ).all()
    assert {(member.tenant_id, member.role) for member in memberships} == {
        (owner.tenant_id, Role.TENANT_ADMIN),
        (second_tenant.id, Role.AUDITOR),
    }

    tokens = auth_service.login(
        email="owner@example.com",
        password="Correct-Horse-Battery-99",
        tenant_id=second_tenant.id,
    )
    principal = auth_service.authenticate_access_token(tokens.access_token)
    assert principal.tenant_id == second_tenant.id
    assert principal.roles == (Role.AUDITOR,)

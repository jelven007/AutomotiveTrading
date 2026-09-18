from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import uuid4

import structlog.contextvars
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from identity_tenant.auth import (
    AuthenticationError,
    AuthService,
    AuthSettings,
    Principal,
    RefreshTokenReuseError,
    RegistrationError,
)
from identity_tenant.config import get_settings
from identity_tenant.context import bind_trace_id, current_trace_id
from identity_tenant.db import database_is_ready, get_session
from identity_tenant.models import Role, Tenant
from identity_tenant.observability import configure_observability
from identity_tenant.rbac import AuthorizationError, Permission, require_permission

bearer = HTTPBearer(auto_error=False)


class RegistrationRequest(BaseModel):
    email: str
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    tenant_name: str = Field(min_length=1, max_length=160)


class LoginRequest(BaseModel):
    email: str
    password: str
    tenant_id: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int


class TotpCodeRequest(BaseModel):
    code: str = Field(pattern=r"^\d{6}$")


class MemberRequest(BaseModel):
    user_id: str
    role: Role


def create_app(auth_settings: AuthSettings | None = None) -> FastAPI:
    if auth_settings is None:
        service_settings = get_settings()
        resolved_settings = service_settings.auth_settings()
        log_level = service_settings.log_level
    else:
        resolved_settings = auth_settings
        log_level = "INFO"
    app = FastAPI(title="identity-tenant")
    configure_observability(app, "identity-tenant", log_level)

    @app.middleware("http")
    async def trace_context(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        trace_id = request.headers.get("X-Trace-ID") or str(uuid4())
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(trace_id=trace_id)
        with bind_trace_id(trace_id):
            response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id
        return response

    def get_auth_service(
        session: Annotated[Session, Depends(get_session)],
    ) -> AuthService:
        return AuthService(session, resolved_settings)

    def get_principal(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> Principal:
        if credentials is None:
            raise AuthenticationError("bearer token is required")
        return service.authenticate_access_token(credentials.credentials)

    @app.exception_handler(AuthenticationError)
    async def authentication_error_handler(
        _: Request,
        error: AuthenticationError,
    ) -> JSONResponse:
        code = (
            "auth.refresh_token_reused"
            if isinstance(error, RefreshTokenReuseError)
            else "auth.invalid"
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "code": code,
                "message": str(error),
                "trace_id": current_trace_id(),
                "details": {},
            },
        )

    @app.exception_handler(RegistrationError)
    async def registration_error_handler(_: Request, error: RegistrationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "code": "registration.invalid",
                "message": str(error),
                "trace_id": current_trace_id(),
                "details": {},
            },
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_error_handler(_: Request, error: AuthorizationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "code": "authorization.denied",
                "message": str(error),
                "trace_id": current_trace_id(),
                "details": {},
            },
        )

    @app.get("/health/live")
    def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", response_model=None)
    def readiness() -> dict[str, str] | JSONResponse:
        if not database_is_ready():
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return {"status": "ready"}

    @app.post("/api/v1/auth/register", response_model=TokenResponse, status_code=201)
    def register(
        payload: RegistrationRequest,
        service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> TokenResponse:
        registration = service.register(**payload.model_dump())
        return TokenResponse(
            **service.login(
                email=payload.email,
                password=payload.password,
                tenant_id=registration.tenant_id,
            ).__dict__
        )

    @app.post("/api/v1/auth/login", response_model=TokenResponse)
    def login(
        payload: LoginRequest,
        service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> TokenResponse:
        return TokenResponse(**service.login(**payload.model_dump()).__dict__)

    @app.post("/api/v1/auth/refresh", response_model=TokenResponse)
    def refresh(
        payload: RefreshRequest,
        service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> TokenResponse:
        return TokenResponse(**service.refresh(payload.refresh_token).__dict__)

    @app.post("/api/v1/auth/logout", status_code=204)
    def logout(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> None:
        if credentials is None:
            raise AuthenticationError("bearer token is required")
        service.logout(credentials.credentials)

    @app.post("/api/v1/auth/mfa/totp/enroll")
    def enroll_totp(
        principal: Annotated[Principal, Depends(get_principal)],
        service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> dict[str, str]:
        enrollment = service.begin_totp_enrollment(principal.user_id)
        return {
            "secret": enrollment.secret,
            "provisioning_uri": enrollment.provisioning_uri,
        }

    @app.post("/api/v1/auth/mfa/totp/verify")
    def verify_totp(
        payload: TotpCodeRequest,
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
        service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> dict[str, str]:
        if credentials is None:
            raise AuthenticationError("bearer token is required")
        access_token = service.verify_totp(credentials.credentials, payload.code)
        return {"access_token": access_token, "token_type": "Bearer"}

    @app.post("/api/v1/tenants/{tenant_id}/members", status_code=201)
    def add_tenant_member(
        tenant_id: str,
        payload: MemberRequest,
        principal: Annotated[Principal, Depends(get_principal)],
        service: Annotated[AuthService, Depends(get_auth_service)],
    ) -> dict[str, str]:
        if principal.tenant_id != tenant_id:
            raise HTTPException(status_code=404, detail="Resource not found")
        require_permission(principal.roles, Permission.MEMBER_MANAGE)
        member = service.add_member(
            actor_user_id=principal.user_id,
            actor_tenant_id=principal.tenant_id,
            tenant_id=tenant_id,
            user_id=payload.user_id,
            role=payload.role,
        )
        return {
            "id": member.id,
            "tenant_id": member.tenant_id,
            "user_id": member.user_id,
            "role": member.role.value,
        }

    @app.get("/api/v1/tenants/{tenant_id}")
    def get_tenant(
        tenant_id: str,
        principal: Annotated[Principal, Depends(get_principal)],
        session: Annotated[Session, Depends(get_session)],
        x_tenant_id: Annotated[str | None, Header()] = None,
    ) -> dict[str, str]:
        del x_tenant_id
        if principal.tenant_id != tenant_id:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "resource.not_found",
                    "message": "Resource not found",
                    "trace_id": current_trace_id(),
                    "details": {},
                },
            )
        tenant = session.get(Tenant, principal.tenant_id)
        if tenant is None:
            raise HTTPException(status_code=404, detail="Resource not found")
        return {"id": tenant.id, "name": tenant.name, "status": tenant.status}

    @app.exception_handler(HTTPException)
    async def http_error_handler(_: Request, error: HTTPException) -> JSONResponse:
        if isinstance(error.detail, dict):
            return JSONResponse(status_code=error.status_code, content=error.detail)
        return JSONResponse(
            status_code=error.status_code,
            content={
                "code": "http.error",
                "message": str(error.detail),
                "trace_id": current_trace_id(),
                "details": {},
            },
        )

    return app

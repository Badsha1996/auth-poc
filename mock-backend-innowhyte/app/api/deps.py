"""Authentication and authorization dependencies.

Authentication: the bearer token is verified by the configured AuthProvider (signature, algorithm,
issuer, expiry). The backend never trusts the frontend's word for who the user is.

Authorization: the role and active flag are read from our database on every request, so a role
change or suspension takes effect immediately, even while the user's access token is still valid.
"""

import logging
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthError, AuthProvider, AuthUnavailableError, Identity, get_auth_provider
from app.core.config import settings
from app.core.request_context import RequestContext, get_request_context
from app.db.session import get_db
from app.models.user import User, UserRole
from app.services import audit_service, user_service

bearer_scheme = HTTPBearer(auto_error=False)
logger = logging.getLogger("app.auth")


def _describe_rejected_token(token: str) -> str:
    # Diagnostics only: the token was already rejected, nothing here is trusted. Logs claim names and iss
    # (public values), never the token, so a misconfigured issuer/claim is visible without leaking secrets.
    try:
        claims = jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return "unparseable token"
    return f"iss={claims.get('iss')!r} claims={sorted(claims)}"


# scope="function": commit/rollback finishes before the response is sent, so a failed commit is a 500,
# never a 200 for a change that was not saved.
DbSession = Annotated[AsyncSession, Depends(get_db, scope="function")]
Ctx = Annotated[RequestContext, Depends(get_request_context)]
Provider = Annotated[AuthProvider, Depends(get_auth_provider)]

_UNAUTHORIZED_HEADERS = {"WWW-Authenticate": "Bearer"}


def get_identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    provider: Provider,
) -> Identity:
    # Sync on purpose: fetching signing keys can block, so FastAPI runs this in a worker thread.
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated", headers=_UNAUTHORIZED_HEADERS)
    try:
        return provider.verify_access_token(credentials.credentials)
    except AuthUnavailableError:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication service unavailable"
        ) from None
    except AuthError as exc:
        detail = _describe_rejected_token(credentials.credentials)
        logger.warning("access token rejected: %s (%s)", exc, detail)
        message = "Invalid or expired token"
        if settings.ENVIRONMENT == "local":
            # Local dev only: surface the reason so it shows up in the Next.js log too.
            # Naming the backend's provider makes a frontend/backend AUTH_PROVIDER mismatch obvious.
            message = f"{message}: {exc} ({detail}; backend AUTH_PROVIDER={provider.name})"
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, message, headers=_UNAUTHORIZED_HEADERS) from None


CurrentIdentity = Annotated[Identity, Depends(get_identity)]


async def get_current_user(db: DbSession, identity: CurrentIdentity, ctx: Ctx, request: Request) -> User:
    user = await user_service.get_by_identity(db, identity)
    if user is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "User not registered. Call POST /users/sync after login."
        )
    if not user.is_active:
        await audit_service.record_detached(
            action="authz.account.denied",
            outcome="denied",
            ctx=ctx,
            actor=user,
            details={"reason": "account_suspended", "path": request.url.path},
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_admin(user: CurrentUser, ctx: Ctx, request: Request) -> User:
    # Role comes from the database, never from the client or the token.
    if user.role != UserRole.ADMIN:
        await audit_service.record_detached(
            action="authz.admin.denied",
            outcome="denied",
            ctx=ctx,
            actor=user,
            details={"path": request.url.path, "method": request.method, "role": user.role.value},
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin role required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]

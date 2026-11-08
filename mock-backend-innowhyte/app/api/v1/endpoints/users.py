import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.api.deps import AdminUser, Ctx, CurrentIdentity, CurrentUser, DbSession, Provider
from app.auth import AuthUnavailableError
from app.integrations.workos_client import WorkOSAPIError
from app.models.user import User
from app.schemas.user import RoleUpdate, StatusUpdate, StatusUpdateResult, UserList, UserRead
from app.services import audit_service, user_service

logger = logging.getLogger("app.users")

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/sync",
    response_model=UserRead,
    summary="Create or update the logged-in user",
    description=(
        "Called by the frontend right after login. The backend verifies the token itself and reads the "
        "profile from the identity provider; nothing in the request body is trusted."
    ),
)
async def sync_current_user(
    db: DbSession, identity: CurrentIdentity, provider: Provider, ctx: Ctx, background: BackgroundTasks
) -> UserRead:
    try:
        profile = await provider.get_profile(identity)
    except (AuthUnavailableError, WorkOSAPIError) as exc:
        logger.error("profile lookup failed for %s: %s", identity.subject, exc)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Identity provider unavailable") from None

    try:
        result = await user_service.upsert_on_login(db, identity, profile)
    except user_service.EmailInUseError as exc:
        await audit_service.record_detached(
            action="user.account.link_denied",
            outcome="denied",
            ctx=ctx,
            actor_external_id=identity.subject,
            details={"reason": "email_in_use"},
        )
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None

    user, created = result.user, result.created
    if not user.is_active:
        await audit_service.record_detached(
            action="user.session.denied",
            outcome="denied",
            ctx=ctx,
            actor=user,
            details={"reason": "suspended"},
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account suspended")

    if result.relinked_from:
        # Same transaction as the relink, so the move and its record commit together.
        audit_service.record(
            db,
            action="user.account.relinked",
            outcome="success",
            ctx=ctx,
            actor=user,
            target_type="user",
            target_id=str(user.id),
            details={"from": result.relinked_from, "to": f"{identity.provider}:{identity.subject}"},
        )

    event = audit_service.record(
        db,
        action="user.account.created" if created else "user.session.started",
        outcome="success",
        ctx=ctx,
        actor=user,
        target_type="user",
        target_id=str(user.id),
        details={"role": user.role.value, "session_id": identity.session_id},
    )
    background.add_task(audit_service.forward_to_workos, event, target_name=user.email)
    return UserRead.model_validate(user)


@router.get("/me", response_model=UserRead, summary="The logged-in user, with role")
async def read_me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)


@router.get("", response_model=UserList, summary="List all users (admin only)")
async def list_users(
    db: DbSession,
    _admin: AdminUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> UserList:
    users, total = await user_service.list_users(db, limit=limit, offset=offset)
    return UserList(
        items=[UserRead.model_validate(u) for u in users], total=total, limit=limit, offset=offset
    )


async def _load_target(db: DbSession, user_id: uuid.UUID) -> User:
    target = await user_service.get_by_id(db, user_id, for_update=True)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return target


@router.patch("/{user_id}/role", response_model=UserRead, summary="Change a user's role (admin only)")
async def change_role(
    user_id: uuid.UUID,
    body: RoleUpdate,
    db: DbSession,
    admin: AdminUser,
    ctx: Ctx,
    background: BackgroundTasks,
) -> UserRead:
    target = await _load_target(db, user_id)
    try:
        previous = await user_service.set_role(db, actor=admin, target=target, role=body.role)
    except user_service.ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None

    if previous != body.role:
        event = audit_service.record(
            db,
            action="user.role.updated",
            outcome="success",
            ctx=ctx,
            actor=admin,
            target_type="user",
            target_id=str(target.id),
            details={"from": previous.value, "to": body.role.value, "target_email": target.email},
        )
        background.add_task(audit_service.forward_to_workos, event, target_name=target.email)
    return UserRead.model_validate(target)


@router.patch(
    "/{user_id}/status",
    response_model=StatusUpdateResult,
    summary="Suspend or restore a user's access (admin only)",
    description="Suspending blocks the user on the next request and ends their sessions at the provider.",
)
async def change_status(
    user_id: uuid.UUID,
    body: StatusUpdate,
    db: DbSession,
    admin: AdminUser,
    provider: Provider,
    ctx: Ctx,
    background: BackgroundTasks,
) -> StatusUpdateResult:
    target = await _load_target(db, user_id)
    try:
        previous = await user_service.set_active(db, actor=admin, target=target, is_active=body.is_active)
    except user_service.ConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from None

    revoked = 0
    if previous != body.is_active:
        if not body.is_active:
            try:
                revoked = await provider.revoke_sessions(target.external_id)
            except Exception:
                # The DB flag already blocks every request; session revocation is defence in depth.
                logger.exception("could not revoke sessions for %s", target.external_id)
        event = audit_service.record(
            db,
            action="user.access.restored" if body.is_active else "user.access.suspended",
            outcome="success",
            ctx=ctx,
            actor=admin,
            target_type="user",
            target_id=str(target.id),
            details={"target_email": target.email, "sessions_revoked": revoked},
        )
        background.add_task(audit_service.forward_to_workos, event, target_name=target.email)
    return StatusUpdateResult(user=UserRead.model_validate(target), sessions_revoked=revoked)

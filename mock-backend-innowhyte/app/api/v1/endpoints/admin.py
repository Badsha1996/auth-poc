from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from app.api.deps import AdminUser, Ctx, DbSession
from app.auth import get_workos_client
from app.core.config import settings
from app.integrations.workos_client import WorkOSAPIError
from app.schemas.user import AuditEventRead, PortalLinkRequest, PortalLinkResponse
from app.services import audit_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-events", response_model=list[AuditEventRead], summary="Recent audit events (admin only)")
async def list_audit_events(
    db: DbSession,
    _admin: AdminUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[AuditEventRead]:
    events = await audit_service.list_events(db, limit=limit, offset=offset)
    return [AuditEventRead.model_validate(e) for e in events]


@router.post(
    "/portal-link",
    response_model=PortalLinkResponse,
    summary="One-time WorkOS Admin Portal link (admin only)",
    description=(
        "Opens the WorkOS Admin Portal for this deployment's organization, where your IT admin can set up "
        "Microsoft Entra ID SSO or verify the company domain. Links are single-use and expire quickly."
    ),
)
async def create_portal_link(
    body: PortalLinkRequest, db: DbSession, admin: AdminUser, ctx: Ctx, background: BackgroundTasks
) -> PortalLinkResponse:
    if settings.AUTH_PROVIDER != "workos":
        raise HTTPException(status.HTTP_501_NOT_IMPLEMENTED, "The Admin Portal needs AUTH_PROVIDER=workos")
    client = get_workos_client()
    if client is None or not settings.WORKOS_ORGANIZATION_ID:
        raise HTTPException(
            status.HTTP_501_NOT_IMPLEMENTED, "Set WORKOS_ORGANIZATION_ID to use the Admin Portal"
        )
    try:
        link = await client.generate_portal_link(
            settings.WORKOS_ORGANIZATION_ID, body.intent, return_url=settings.CORS_ORIGINS[0] + "/admin"
        )
    except WorkOSAPIError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"WorkOS refused the request ({exc.status_code})"
        ) from None

    event = audit_service.record(
        db,
        action="admin_portal.link.created",
        outcome="success",
        ctx=ctx,
        actor=admin,
        target_type="organization",
        target_id=settings.WORKOS_ORGANIZATION_ID,
        details={"intent": body.intent},
    )
    background.add_task(audit_service.forward_to_workos, event)
    return PortalLinkResponse(link=link)

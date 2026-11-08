"""Security audit trail.

Every security-relevant action is written to the append-only `audit_events` table, in the same
transaction as the change it describes, so a change can never exist without its audit row.
Optionally the event is also sent to WorkOS Audit Logs (best effort, after the response is sent).
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_workos_client
from app.core.config import settings
from app.core.request_context import RequestContext
from app.db.session import SessionLocal
from app.models.audit_event import AuditEvent
from app.models.user import User

logger = logging.getLogger("app.audit")

# Actions that are also forwarded to WorkOS Audit Logs when enabled ({group}.{object}.{action} naming).
WORKOS_FORWARDED_ACTIONS = {
    "user.account.created",
    "user.role.updated",
    "user.access.suspended",
    "user.access.restored",
    "admin_portal.link.created",
}


def _build(
    *,
    action: str,
    outcome: str,
    ctx: RequestContext,
    actor: User | None = None,
    actor_external_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    return AuditEvent(
        id=uuid.uuid4(),
        occurred_at=datetime.now(UTC),
        action=action,
        outcome=outcome,
        actor_user_id=actor.id if actor else None,
        actor_external_id=actor.external_id if actor else actor_external_id,
        actor_email=actor.email if actor else None,
        target_type=target_type,
        target_id=target_id,
        ip_address=ctx.ip_address,
        user_agent=ctx.user_agent,
        request_id=ctx.request_id,
        details=details or {},
    )


def record(db: AsyncSession, **kwargs: Any) -> AuditEvent:
    """Add an audit event to the current transaction (committed together with the change)."""
    event = _build(**kwargs)
    db.add(event)
    logger.info("audit %s %s target=%s", event.action, event.outcome, event.target_id)
    return event


async def record_detached(**kwargs: Any) -> None:
    """Write an audit event in its own transaction.

    Used for denials: the request's own transaction is rolled back when it raises 401/403,
    but the denial must still be recorded.
    """
    event = _build(**kwargs)
    logger.warning("audit %s %s actor=%s", event.action, event.outcome, event.actor_external_id)
    try:
        async with SessionLocal() as session:
            session.add(event)
            await session.commit()
    except Exception:  # never turn a 403 into a 500 because auditing failed
        logger.exception("failed to write audit event %s", event.action)


async def list_events(db: AsyncSession, *, limit: int, offset: int) -> list[AuditEvent]:
    rows = await db.scalars(
        select(AuditEvent).order_by(AuditEvent.occurred_at.desc()).limit(limit).offset(offset)
    )
    return list(rows)


async def forward_to_workos(event: AuditEvent, *, target_name: str | None = None) -> None:
    """Send an event to WorkOS Audit Logs. Best effort: the local table is the source of truth."""
    client = get_workos_client()
    if not (
        settings.WORKOS_AUDIT_LOGS_ENABLED
        and client
        and settings.WORKOS_ORGANIZATION_ID
        and event.action in WORKOS_FORWARDED_ACTIONS
    ):
        return
    payload = {
        "action": event.action,
        "occurred_at": event.occurred_at.isoformat(),
        "version": 1,
        "actor": {
            "type": "user",
            "id": event.actor_external_id or "system",
            "name": event.actor_email or "system",
            "metadata": {},  # the registered schema requires the object, even when empty
        },
        "targets": [
            {"type": event.target_type or "unknown", "id": event.target_id or "unknown", "name": target_name}
        ],
        "context": {"location": event.ip_address or "0.0.0.0", "user_agent": event.user_agent or "unknown"},
        # WorkOS limits: 50 keys, 500-char values; schemas registered by scripts/setup_workos_audit_schemas.py
        # Every key in the schema is required, so missing values are sent as "".
        "metadata": {k: "" if v is None else str(v)[:500] for k, v in list(event.details.items())[:50]},
    }
    try:
        await client.create_audit_event(
            settings.WORKOS_ORGANIZATION_ID, payload, idempotency_key=str(event.id)
        )
    except Exception:
        logger.exception("failed to forward audit event %s to WorkOS", event.id)

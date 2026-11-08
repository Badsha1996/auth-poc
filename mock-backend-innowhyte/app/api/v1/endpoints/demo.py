"""Two endpoints that show role-based access: one for every signed-in user, one for admins only."""

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import func, select

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.models.user import User, UserRole

router = APIRouter(prefix="/demo", tags=["demo"])


@router.get("/member", summary="Any signed-in, active user")
async def member_area(user: CurrentUser) -> dict:
    return {
        "area": "member",
        "message": f"Hello {user.full_name or user.email}. Every signed-in user can call this endpoint.",
        "your_role": user.role.value,
        "checked_at": datetime.now(UTC).isoformat(),
    }


@router.get("/admin", summary="Admins only")
async def admin_area(db: DbSession, admin: AdminUser) -> dict:
    rows = (await db.execute(select(User.role, func.count()).group_by(User.role))).all()
    counts = {role.value: n for role, n in rows}
    suspended = await db.scalar(select(func.count()).select_from(User).where(User.is_active.is_(False))) or 0
    return {
        "area": "admin",
        "message": f"Welcome {admin.full_name or admin.email}. Only admins can call this endpoint.",
        "stats": {
            "admins": counts.get(UserRole.ADMIN.value, 0),
            "users": counts.get(UserRole.USER.value, 0),
            "suspended": suspended,
        },
        "checked_at": datetime.now(UTC).isoformat(),
    }

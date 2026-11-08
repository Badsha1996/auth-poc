import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Identity, Profile
from app.core.config import settings
from app.models.user import User, UserRole


class ConflictError(Exception):
    """The change is valid input but not allowed in the current state. Maps to 409."""


class EmailInUseError(ConflictError):
    pass


def is_break_glass_admin(user: User) -> bool:
    return user.email is not None and user.email.lower() in settings.ADMIN_EMAILS


async def get_by_identity(db: AsyncSession, identity: Identity) -> User | None:
    return await db.scalar(
        select(User).where(User.auth_provider == identity.provider, User.external_id == identity.subject)
    )


async def get_by_id(db: AsyncSession, user_id: uuid.UUID, *, for_update: bool = False) -> User | None:
    stmt = select(User).where(User.id == user_id)
    if for_update:
        stmt = stmt.with_for_update()
    return await db.scalar(stmt)


@dataclass(frozen=True, slots=True)
class LoginResult:
    user: User
    created: bool
    # Set when an existing account was moved over from another auth provider: "provider:external_id".
    relinked_from: str | None = None


async def _relink_if_provider_switched(
    db: AsyncSession, identity: Identity, profile: Profile, email: str
) -> str | None:
    """Handle an email that already belongs to a different identity.

    Same provider, different user id: a genuine conflict (two accounts claim one email) -> EmailInUseError.
    Different provider: the deployment switched AUTH_PROVIDER (e.g. WorkOS -> Better Auth). If the new
    provider has verified the email, the existing row is moved to the new identity, so the person keeps
    their role and audit history. An unverified email never takes over an account.
    """
    owner = await db.scalar(select(User).where(User.email == email).with_for_update())
    if owner is None or (owner.auth_provider, owner.external_id) == (identity.provider, identity.subject):
        return None
    if owner.auth_provider == identity.provider or not profile.email_verified:
        raise EmailInUseError("This email is already linked to another account")
    if await get_by_identity(db, identity) is not None:
        # The new identity already has its own row (another email); rows are never merged automatically.
        raise EmailInUseError("This email is already linked to another account")
    previous = f"{owner.auth_provider}:{owner.external_id}"
    owner.auth_provider = identity.provider
    owner.external_id = identity.subject
    await db.flush()
    return previous


async def upsert_on_login(db: AsyncSession, identity: Identity, profile: Profile) -> LoginResult:
    """Create the user on first login, otherwise refresh profile + last_login_at.

    Uses INSERT ... ON CONFLICT so concurrent first logins can't create duplicates. The role is never
    taken from the client: new users get `user`, and emails listed in ADMIN_EMAILS get `admin`, but only
    once the provider has verified that email address.
    """
    email = profile.email.lower() if profile.email else None
    relinked_from = await _relink_if_provider_switched(db, identity, profile, email) if email else None

    values = {
        "auth_provider": identity.provider,
        "external_id": identity.subject,
        "email": email,
        "email_verified": profile.email_verified,
        "full_name": profile.full_name,
        "avatar_url": profile.avatar_url,
        "last_login_at": datetime.now(UTC),
    }
    is_bootstrap_admin = bool(email and profile.email_verified and email in settings.ADMIN_EMAILS)
    if is_bootstrap_admin:
        values["role"] = UserRole.ADMIN

    stmt = insert(User).values(**values)
    update_cols = {
        "email": stmt.excluded.email,
        "email_verified": stmt.excluded.email_verified,
        "full_name": func.coalesce(stmt.excluded.full_name, User.full_name),
        "avatar_url": func.coalesce(stmt.excluded.avatar_url, User.avatar_url),
        "last_login_at": stmt.excluded.last_login_at,
        "updated_at": func.now(),
    }
    if is_bootstrap_admin:
        update_cols["role"] = stmt.excluded.role

    stmt = stmt.on_conflict_do_update(
        index_elements=[User.auth_provider, User.external_id], set_=update_cols
    ).returning(User, literal_column("(xmax = 0)").label("created"))
    row = (await db.execute(stmt.execution_options(populate_existing=True))).one()
    return LoginResult(user=row[0], created=bool(row[1]), relinked_from=relinked_from)


async def list_users(db: AsyncSession, *, limit: int, offset: int) -> tuple[list[User], int]:
    total = await db.scalar(select(func.count()).select_from(User)) or 0
    rows = await db.scalars(select(User).order_by(User.created_at.desc()).limit(limit).offset(offset))
    return list(rows), total


async def _other_active_admins(db: AsyncSession, exclude: uuid.UUID) -> int:
    # Lock the admin rows so two admins can't demote each other at the same time and leave none.
    ids = await db.scalars(
        select(User.id)
        .where(User.role == UserRole.ADMIN, User.is_active.is_(True), User.id != exclude)
        .with_for_update()
    )
    return len(list(ids))


def _guard_self_and_break_glass(actor: User, target: User, action: str) -> None:
    if actor.id == target.id:
        raise ConflictError(f"You can't {action} your own account. Ask another admin.")
    if is_break_glass_admin(target):
        raise ConflictError("This admin is set in ADMIN_EMAILS on the server and can't be changed here.")


async def set_role(db: AsyncSession, *, actor: User, target: User, role: UserRole) -> UserRole:
    """Change a user's role. Returns the previous role."""
    _guard_self_and_break_glass(actor, target, "change the role of")
    previous = target.role
    if previous == role:
        return previous
    if previous == UserRole.ADMIN and await _other_active_admins(db, target.id) == 0:
        raise ConflictError("At least one active admin must remain.")
    target.role = role
    await db.flush()
    await db.refresh(target)  # reload server-generated updated_at
    return previous


async def set_active(db: AsyncSession, *, actor: User, target: User, is_active: bool) -> bool:
    """Suspend or restore access. Returns the previous state."""
    _guard_self_and_break_glass(actor, target, "suspend")
    previous = target.is_active
    if previous == is_active:
        return previous
    if not is_active and target.role == UserRole.ADMIN and await _other_active_admins(db, target.id) == 0:
        raise ConflictError("At least one active admin must remain.")
    target.is_active = is_active
    target.deactivated_at = None if is_active else datetime.now(UTC)
    await db.flush()
    await db.refresh(target)  # reload server-generated updated_at
    return previous

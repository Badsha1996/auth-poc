"""Switching AUTH_PROVIDER (e.g. WorkOS -> Better Auth) keeps people's accounts, roles and history.

The test app runs with AUTH_PROVIDER=jwt, so a row created "by WorkOS" is inserted directly and then the
same person signs in through the current (jwt) provider.
"""

import uuid

from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import AuditEvent, User
from app.models.user import UserRole
from tests.conftest import auth, make_token

SYNC = "/api/v1/users/sync"


async def _insert_workos_user(email: str, role: UserRole = UserRole.USER) -> uuid.UUID:
    async with SessionLocal() as s:
        user = User(
            auth_provider="workos",
            external_id=f"user_{uuid.uuid4().hex[:12]}",
            email=email,
            email_verified=True,
            role=role,
        )
        s.add(user)
        await s.commit()
        return user.id


async def test_verified_email_moves_account_to_new_provider(client):
    user_id = await _insert_workos_user("switcher@example.com", role=UserRole.ADMIN)

    r = await client.post(SYNC, headers=auth(make_token("jwt_switcher", "switcher@example.com")))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == str(user_id)  # same account, not a new one
    assert body["role"] == "admin"  # role survives the switch
    assert body["auth_provider"] == "jwt"
    assert body["external_id"] == "jwt_switcher"

    async with SessionLocal() as s:
        event = await s.scalar(
            select(AuditEvent).where(
                AuditEvent.action == "user.account.relinked", AuditEvent.target_id == str(user_id)
            )
        )
    assert event is not None
    assert event.details["from"].startswith("workos:user_")
    assert event.details["to"] == "jwt:jwt_switcher"

    # Signing in again is an ordinary login, not another relink.
    r = await client.post(SYNC, headers=auth(make_token("jwt_switcher", "switcher@example.com")))
    assert r.status_code == 200 and r.json()["id"] == str(user_id)


async def test_unverified_email_cannot_take_over_account(client):
    user_id = await _insert_workos_user("victim@example.com", role=UserRole.ADMIN)

    token = make_token("jwt_attacker", "victim@example.com", email_verified=False)
    r = await client.post(SYNC, headers=auth(token))
    assert r.status_code == 409

    async with SessionLocal() as s:
        user = await s.get(User, user_id)
    assert user is not None and user.auth_provider == "workos"  # untouched


async def test_unverified_admin_email_does_not_get_admin(client, monkeypatch):
    monkeypatch.setattr(settings, "ADMIN_EMAILS", [*settings.ADMIN_EMAILS, "new-boss@example.com"])

    token = make_token("jwt_fake_boss", "new-boss@example.com", email_verified=False)
    r = await client.post(SYNC, headers=auth(token))
    assert r.status_code == 200 and r.json()["role"] == "user"

    r = await client.post(SYNC, headers=auth(make_token("jwt_fake_boss", "new-boss@example.com")))
    assert r.status_code == 200 and r.json()["role"] == "admin"  # promoted once the provider verified it

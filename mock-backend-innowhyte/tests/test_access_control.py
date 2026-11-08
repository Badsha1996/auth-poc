import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.db.session import SessionLocal
from app.models import AuditEvent
from tests.conftest import login

API = "/api/v1"


async def _admin(client):
    return await login(client, "admin_1", "boss@example.com", "The Boss")


async def _latest(action: str) -> AuditEvent | None:
    async with SessionLocal() as s:
        return await s.scalar(
            select(AuditEvent)
            .where(AuditEvent.action == action)
            .order_by(AuditEvent.occurred_at.desc())
            .limit(1)
        )


async def test_demo_endpoints_by_role(client):
    admin_h, _ = await _admin(client)
    user_h, _ = await login(client, "demo_user", "demo@example.com")

    assert (await client.get(f"{API}/demo/member", headers=user_h)).status_code == 200
    assert (await client.get(f"{API}/demo/member", headers=admin_h)).status_code == 200

    denied = await client.get(f"{API}/demo/admin", headers=user_h)
    assert denied.status_code == 403
    ok = await client.get(f"{API}/demo/admin", headers=admin_h)
    assert ok.status_code == 200
    assert ok.json()["stats"]["admins"] >= 1

    event = await _latest("authz.admin.denied")
    assert event is not None and event.actor_email == "demo@example.com"
    assert event.outcome == "denied" and event.details["path"] == f"{API}/demo/admin"


async def test_admin_promotes_user_and_change_is_immediate(client):
    admin_h, _ = await _admin(client)
    user_h, user = await login(client, "promo_user", "promo@example.com")
    assert (await client.get(f"{API}/demo/admin", headers=user_h)).status_code == 403

    r = await client.patch(f"{API}/users/{user['id']}/role", headers=admin_h, json={"role": "admin"})
    assert r.status_code == 200 and r.json()["role"] == "admin"

    # Same access token as before: the role is read from the DB on every request.
    assert (await client.get(f"{API}/demo/admin", headers=user_h)).status_code == 200

    event = await _latest("user.role.updated")
    assert event is not None and event.target_id == user["id"]
    assert event.details["from"] == "user" and event.details["to"] == "admin"
    assert event.actor_email == "boss@example.com"

    r = await client.patch(f"{API}/users/{user['id']}/role", headers=admin_h, json={"role": "user"})
    assert r.status_code == 200 and r.json()["role"] == "user"


async def test_normal_user_cannot_change_roles(client):
    user_h, user = await login(client, "sneaky", "sneaky@example.com")
    r = await client.patch(f"{API}/users/{user['id']}/role", headers=user_h, json={"role": "admin"})
    assert r.status_code == 403


async def test_admin_cannot_change_own_role_or_suspend_self(client):
    admin_h, admin = await _admin(client)
    assert (
        await client.patch(f"{API}/users/{admin['id']}/role", headers=admin_h, json={"role": "user"})
    ).status_code == 409
    assert (
        await client.patch(f"{API}/users/{admin['id']}/status", headers=admin_h, json={"is_active": False})
    ).status_code == 409


async def test_break_glass_admin_cannot_be_demoted_by_other_admin(client):
    admin_h, boss = await _admin(client)
    other_h, other = await login(client, "second_admin", "second@example.com")
    await client.patch(f"{API}/users/{other['id']}/role", headers=admin_h, json={"role": "admin"})

    r = await client.patch(f"{API}/users/{boss['id']}/role", headers=other_h, json={"role": "user"})
    assert r.status_code == 409
    assert "ADMIN_EMAILS" in r.json()["detail"]


async def test_invalid_input_is_rejected(client):
    admin_h, _ = await _admin(client)
    _, user = await login(client, "input_user", "input@example.com")
    assert (
        await client.patch(f"{API}/users/{user['id']}/role", headers=admin_h, json={"role": "owner"})
    ).status_code == 422
    assert (
        await client.patch(f"{API}/users/{user['id']}/role", headers=admin_h, json={"role": "user", "x": 1})
    ).status_code == 422
    assert (
        await client.patch(f"{API}/users/{uuid.uuid4()}/role", headers=admin_h, json={"role": "user"})
    ).status_code == 404


async def test_suspend_blocks_access_immediately_then_restore(client):
    admin_h, _ = await _admin(client)
    user_h, user = await login(client, "suspend_me", "suspend@example.com")

    r = await client.patch(f"{API}/users/{user['id']}/status", headers=admin_h, json={"is_active": False})
    assert r.status_code == 200
    assert r.json()["user"]["is_active"] is False
    assert r.json()["user"]["deactivated_at"] is not None

    blocked = await client.get(f"{API}/demo/member", headers=user_h)
    assert blocked.status_code == 403 and blocked.json()["detail"] == "Account suspended"
    assert (await client.post(f"{API}/users/sync", headers=user_h)).status_code == 403
    assert (await _latest("user.access.suspended")).target_id == user["id"]

    r = await client.patch(f"{API}/users/{user['id']}/status", headers=admin_h, json={"is_active": True})
    assert r.status_code == 200
    assert (await client.get(f"{API}/demo/member", headers=user_h)).status_code == 200


async def test_audit_events_admin_only(client):
    admin_h, _ = await _admin(client)
    user_h, _ = await login(client, "audit_reader", "reader@example.com")
    assert (await client.get(f"{API}/admin/audit-events", headers=user_h)).status_code == 403
    r = await client.get(f"{API}/admin/audit-events", headers=admin_h, params={"limit": 5})
    assert r.status_code == 200
    assert 0 < len(r.json()) <= 5


async def test_portal_link_needs_organization(client):
    admin_h, _ = await _admin(client)
    r = await client.post(f"{API}/admin/portal-link", headers=admin_h, json={"intent": "sso"})
    assert r.status_code == 501


@pytest.mark.parametrize(
    "statement",
    ["UPDATE audit_events SET action = 'tampered'", "DELETE FROM audit_events", "TRUNCATE audit_events"],
)
async def test_audit_events_are_append_only(client, statement):
    await _admin(client)  # guarantees at least one row
    async with SessionLocal() as s:
        with pytest.raises(DBAPIError, match="append-only"):
            await s.execute(text(statement))
        await s.rollback()

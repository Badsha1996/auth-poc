from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import AuditEvent
from tests.conftest import auth, login, make_token

URL = "/api/v1/users"


async def _actions_for(target_id: str) -> list[str]:
    async with SessionLocal() as s:
        rows = await s.scalars(
            select(AuditEvent.action)
            .where(AuditEvent.target_id == target_id)
            .order_by(AuditEvent.occurred_at)
        )
        return list(rows)


async def test_sync_creates_then_updates_user_and_audits(client):
    token = make_token("user_1", "alice@example.com", "Alice")

    r1 = await client.post(f"{URL}/sync", headers=auth(token))
    assert r1.status_code == 200
    body = r1.json()
    assert body["email"] == "alice@example.com"
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert body["auth_provider"] == "jwt"

    r2 = await client.post(f"{URL}/sync", headers=auth(token))
    assert r2.status_code == 200
    assert r2.json()["id"] == body["id"]
    assert r2.json()["last_login_at"] >= body["last_login_at"]

    assert await _actions_for(body["id"]) == ["user.account.created", "user.session.started"]


async def test_role_cannot_be_set_by_client(client):
    token = make_token("user_2", "mallory@example.com")
    r = await client.post(f"{URL}/sync", headers=auth(token), json={"role": "admin"})
    assert r.status_code == 200
    assert r.json()["role"] == "user"


async def test_same_email_on_another_identity_is_rejected(client):
    await login(client, "owner_1", "taken@example.com")
    r = await client.post(f"{URL}/sync", headers=auth(make_token("intruder_1", "taken@example.com")))
    assert r.status_code == 409


async def test_me_returns_role(client):
    headers, _ = await login(client, "user_me", "me@example.com")
    r = await client.get(f"{URL}/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["role"] == "user"


async def test_list_requires_token(client):
    r = await client.get(URL)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


async def test_list_rejects_bad_and_expired_tokens(client):
    assert (await client.get(URL, headers=auth("garbage"))).status_code == 401
    expired = make_token("user_1", exp_in=-60)
    assert (await client.get(URL, headers=auth(expired))).status_code == 401


async def test_list_forbidden_for_unregistered_user(client):
    r = await client.get(URL, headers=auth(make_token("ghost")))
    assert r.status_code == 403


async def test_list_forbidden_for_normal_user(client):
    headers, _ = await login(client, "user_3", "bob@example.com")
    r = await client.get(URL, headers=headers)
    assert r.status_code == 403


async def test_admin_can_list_users(client):
    headers, me = await login(client, "admin_1", "Boss@Example.com", "The Boss")
    assert me["role"] == "admin"

    r = await client.get(URL, headers=headers, params={"limit": 2})
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 3
    assert len(data["items"]) == 2
    assert data["limit"] == 2


async def test_pagination_validation(client):
    headers, _ = await login(client, "admin_1", "boss@example.com")
    r = await client.get(URL, headers=headers, params={"limit": 1000})
    assert r.status_code == 422


async def test_security_headers_and_request_id(client):
    r = await client.get("/health", headers={"X-Request-ID": "req-123"})
    assert r.headers["x-request-id"] == "req-123"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cache-control"] == "no-store"

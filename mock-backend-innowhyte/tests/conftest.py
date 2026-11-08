import os
import subprocess
import sys
import time
from collections.abc import AsyncIterator
from pathlib import Path

# Point the app at a dedicated LOCAL test database and HS256 tokens before importing it.
# Empty values override anything in .env (for example the shared Neon DATABASE_URL).
os.environ.update(
    {
        "POSTGRES_DB": "user_api_test",
        "DATABASE_URL": "",
        "MIGRATIONS_DATABASE_URL": "",
        "AUTH_PROVIDER": "jwt",
        "JWT_JWKS_URL": "",
        "JWT_SECRET": "test-secret-that-is-long-enough-for-hs256",
        "JWT_ALGORITHMS": "HS256",
        "JWT_ISSUER": "",
        "JWT_AUDIENCE": "",
        "ADMIN_EMAILS": "boss@example.com",
        "WORKOS_AUDIT_LOGS_ENABLED": "false",
        "WORKOS_ORGANIZATION_ID": "",
    }
)

import asyncpg  # noqa: E402
import jwt  # noqa: E402
import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import engine  # noqa: E402
from app.main import app  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def _alembic(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "alembic", *args], cwd=ROOT, env=os.environ.copy(), check=True)


@pytest.fixture(scope="session", autouse=True)
async def _database() -> AsyncIterator[None]:
    # Safety net: these fixtures drop the schema, so refuse anything but a local *_test database.
    assert settings.POSTGRES_HOST in {"localhost", "127.0.0.1"}, "tests must run against a local database"
    assert settings.POSTGRES_DB.endswith("_test"), "tests must run against a *_test database"
    assert not settings.DATABASE_URL

    conn = await asyncpg.connect(
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database="postgres",
    )
    if not await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", settings.POSTGRES_DB):
        await conn.execute(f'CREATE DATABASE "{settings.POSTGRES_DB}"')
    await conn.close()

    conn = await asyncpg.connect(
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        database=settings.POSTGRES_DB,
    )
    await conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    await conn.close()

    # Exercise the real migrations, including a full downgrade, exactly as production would run them.
    _alembic("upgrade", "head")
    _alembic("downgrade", "base")
    _alembic("upgrade", "head")
    yield
    await engine.dispose()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def make_token(
    sub: str,
    email: str | None = None,
    name: str | None = None,
    exp_in: int = 300,
    email_verified: bool = True,
) -> str:
    now = int(time.time())
    payload: dict = {"sub": sub, "iat": now, "exp": now + exp_in, "sid": f"session_{sub}"}
    if email:
        payload["email"] = email
        # The provider must say so explicitly; an email claim alone is not treated as verified.
        payload["email_verified"] = email_verified
    if name:
        payload["name"] = name
    return jwt.encode(payload, os.environ["JWT_SECRET"], algorithm="HS256")


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def login(client: AsyncClient, sub: str, email: str, name: str | None = None) -> tuple[dict, dict]:
    """Simulate the frontend: user signs in, then the app calls /users/sync. Returns (headers, user)."""
    headers = auth(make_token(sub, email, name))
    r = await client.post("/api/v1/users/sync", headers=headers)
    assert r.status_code == 200, r.text
    return headers, r.json()

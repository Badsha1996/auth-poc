# User API

FastAPI + PostgreSQL (async SQLAlchemy 2.0) + Pydantic v2 + Alembic.

Login happens in the Next.js app through WorkOS AuthKit. This API never logs anyone in. It:

1. **Authenticates** every request itself: verifies the WorkOS access token (RS256 signature via JWKS,
   pinned algorithm, issuer, `client_id`, `exp`/`iat`, `sid`). It does not trust the frontend.
2. **Authorizes** from its own database: role (`user` / `admin`) and `is_active` are read on every
   request, so a role change or suspension applies immediately, even to an unexpired token.
3. **Audits** every security-relevant action into an append-only `audit_events` table (a trigger
   blocks UPDATE/DELETE/TRUNCATE), optionally mirrored to WorkOS Audit Logs.
4. **Owns the database schema.** Alembic is the only migration tool for this database. The Next.js
   app reads it through Prisma (`prisma db pull`) and never migrates.

## Endpoints

| Method | Path                               | Who        | What |
|--------|------------------------------------|------------|------|
| POST   | `/api/v1/users/sync`               | any login  | Create the user on first login (role `user`), else refresh profile + last login. Profile is fetched from WorkOS, never from the request. |
| GET    | `/api/v1/users/me`                 | any login  | Current user with role |
| GET    | `/api/v1/users`                    | admin      | List users (`?limit=50&offset=0`, max 100) |
| PATCH  | `/api/v1/users/{id}/role`          | admin      | `{"role": "admin" \| "user"}` |
| PATCH  | `/api/v1/users/{id}/status`        | admin      | `{"is_active": false}` suspends and ends the user's WorkOS sessions |
| GET    | `/api/v1/demo/member`              | any login  | Role demo: everyone |
| GET    | `/api/v1/demo/admin`               | admin      | Role demo: admins only |
| GET    | `/api/v1/admin/audit-events`       | admin      | Recent audit events |
| POST   | `/api/v1/admin/portal-link`        | admin      | One-time WorkOS Admin Portal link (`sso`, `domain_verification`) |
| GET    | `/health`                          | public     | API + database check |

Status codes: `401` bad/missing/expired token · `403` not registered, suspended, or not admin ·
`409` blocked change (own account, break-glass admin, last admin) · `503` WorkOS unreachable (fails closed).

Safety rules: admins can't change or suspend themselves; emails in `ADMIN_EMAILS` are always admin
and can't be demoted; the last active admin can't be removed (rows are locked to prevent races).

## Quick start

```bash
cp .env.example .env              # fill in DATABASE_URL, MIGRATIONS_DATABASE_URL, WORKOS_*, ADMIN_EMAILS
python -m venv .venv && .venv/Scripts/activate   # (source .venv/bin/activate on macOS/Linux)
pip install -r requirements-dev.txt
alembic upgrade head              # creates/updates tables in the database
fastapi dev app/main.py           # http://localhost:8000/docs
```

## Migrations (this service owns them)

```bash
# 1. Change or add a model in app/models/
# 2. Generate a migration and READ it (autogenerate misses triggers, data moves, renames)
alembic revision --autogenerate -m "add user department"
# 3. Review the SQL that will run
alembic upgrade head --sql
# 4. Apply (uses MIGRATIONS_DATABASE_URL, the direct non-pooled Neon URL)
alembic upgrade head
# 5. Confirm models and database match
alembic check
# 6. Tell the Next.js app: npm run db:pull && npm run db:generate
```

Roll back one step with `alembic downgrade -1`. The test suite runs `upgrade head → downgrade base →
upgrade head` on every run, so every migration must have a working downgrade.

WorkOS Audit Logs only accepts event types that are registered in the environment. Run
`python -m scripts.setup_workos_audit_schemas` once per WorkOS environment before setting
`WORKOS_AUDIT_LOGS_ENABLED=true`.

## Tests and lint

Tests use a local Docker Postgres (`docker compose up -d --wait`, port 5433) and a separate
`user_api_test` database; they refuse to run against anything else.

```bash
pytest
ruff check . && ruff format .
```

## Layout

```
app/
  auth/                 provider abstraction: AuthProvider protocol, WorkOS + generic JWT providers
  integrations/         WorkOS REST client (profiles, sessions, audit logs, admin portal)
  core/config.py        settings (pydantic-settings, .env)
  core/request_context  IP / user agent / request id for audit events
  db/                   engine (asyncpg, TLS verified), session, Base + naming conventions
  models/               User, AuditEvent
  services/             user rules (upsert, role, suspension guards), audit trail
  api/deps.py           authentication + authorization dependencies
  api/v1/endpoints/     users, demo, admin routes
alembic/                migrations (the single source of truth for the schema)
scripts/                one-off setup (WorkOS audit schemas)
tests/                  integration + token-verification tests
```

"""Register the audit event types this API sends to WorkOS Audit Logs.

WorkOS rejects events whose action/version is not configured in the environment, so run this once
per WorkOS environment (staging, then production) before enabling WORKOS_AUDIT_LOGS_ENABLED:

    python -m scripts.setup_workos_audit_schemas

Creating a schema that already exists makes WorkOS add a new version; this script skips actions
that already have one.
"""

import asyncio
import sys

import httpx

from app.core.config import settings

USER_TARGET = [{"type": "user"}]
SCHEMAS: dict[str, dict] = {
    "user.account.created": {"targets": USER_TARGET, "metadata": ["role", "session_id"]},
    "user.role.updated": {"targets": USER_TARGET, "metadata": ["from", "to", "target_email"]},
    "user.access.suspended": {"targets": USER_TARGET, "metadata": ["target_email", "sessions_revoked"]},
    "user.access.restored": {"targets": USER_TARGET, "metadata": ["target_email", "sessions_revoked"]},
    "admin_portal.link.created": {"targets": [{"type": "organization"}], "metadata": ["intent"]},
}


def _body(spec: dict) -> dict:
    return {
        "actor": {"metadata": {"type": "object", "properties": {}}},
        "targets": spec["targets"],
        "metadata": {"type": "object", "properties": {k: {"type": "string"} for k in spec["metadata"]}},
    }


async def main() -> int:
    if not settings.WORKOS_API_KEY:
        print("WORKOS_API_KEY is not set")
        return 1
    headers = {"Authorization": f"Bearer {settings.WORKOS_API_KEY.get_secret_value()}"}
    async with httpx.AsyncClient(base_url=settings.WORKOS_API_BASE_URL, headers=headers, timeout=15) as http:
        for action, spec in SCHEMAS.items():
            existing = await http.get(f"/audit_logs/actions/{action}/schemas")
            if existing.status_code == 200 and existing.json().get("data"):
                print(f"exists   {action}")
                continue
            r = await http.post(f"/audit_logs/actions/{action}/schemas", json=_body(spec))
            if r.status_code >= 400:
                print(f"FAILED   {action}: {r.status_code} {r.text[:200]}")
                return 1
            print(f"created  {action} (version {r.json().get('version')})")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

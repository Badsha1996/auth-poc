"""Minimal async client for the WorkOS REST API calls this backend needs."""

import logging
import re
import uuid
from typing import Any

import httpx

from app.auth.base import AuthUnavailableError

logger = logging.getLogger("app.workos")

_USER_ID = re.compile(r"^user_[A-Za-z0-9]+$")


class WorkOSAPIError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"WorkOS API error {status_code}: {message}")
        self.status_code = status_code


class WorkOSClient:
    def __init__(self, *, api_key: str, base_url: str, timeout: float = 10.0) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}", "User-Agent": "innowhyte-user-api"},
            timeout=timeout,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise AuthUnavailableError("WorkOS API is unreachable") from exc
        if response.status_code >= 400:
            # Never log the request headers: they carry the API key.
            raise WorkOSAPIError(response.status_code, response.text[:300])
        return response.json() if response.content else None

    @staticmethod
    def _check_user_id(user_id: str) -> str:
        if not _USER_ID.match(user_id):
            raise ValueError("Invalid WorkOS user id")
        return user_id

    async def get_user(self, user_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/user_management/users/{self._check_user_id(user_id)}")

    async def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        data = await self._request(
            "GET", f"/user_management/users/{self._check_user_id(user_id)}/sessions", params={"limit": 100}
        )
        return list(data.get("data", []))

    async def revoke_session(self, session_id: str) -> None:
        await self._request("POST", "/user_management/sessions/revoke", json={"session_id": session_id})

    async def create_audit_event(
        self, organization_id: str, event: dict[str, Any], idempotency_key: str
    ) -> None:
        await self._request(
            "POST",
            "/audit_logs/events",
            json={"organization_id": organization_id, "event": event},
            headers={"Idempotency-Key": idempotency_key},
        )

    async def generate_portal_link(self, organization_id: str, intent: str, return_url: str | None) -> str:
        body: dict[str, Any] = {"organization": organization_id, "intent": intent}
        if return_url:
            body["return_url"] = return_url
        data = await self._request(
            "POST", "/portal/generate_link", json=body, headers={"Idempotency-Key": str(uuid.uuid4())}
        )
        return data["link"]

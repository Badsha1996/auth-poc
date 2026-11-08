import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.user import UserRole


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    auth_provider: str
    external_id: str
    email: EmailStr | None
    email_verified: bool
    full_name: str | None
    avatar_url: str | None
    role: UserRole
    is_active: bool
    deactivated_at: datetime | None
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UserList(BaseModel):
    items: list[UserRead]
    total: int
    limit: int
    offset: int


class RoleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: bool


class StatusUpdateResult(BaseModel):
    user: UserRead
    sessions_revoked: int


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    occurred_at: datetime
    action: str
    outcome: str
    actor_email: str | None
    actor_external_id: str | None
    target_type: str | None
    target_id: str | None
    ip_address: str | None
    request_id: str | None
    details: dict[str, Any]


class PortalLinkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: Literal["sso", "domain_verification", "audit_logs", "log_streams"] = "sso"


class PortalLinkResponse(BaseModel):
    link: str

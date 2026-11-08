"""Provider-neutral auth types.

The rest of the app depends only on these types and on the `AuthProvider` protocol, never on WorkOS
directly. To support another identity provider (for example Better Auth on isolated infrastructure),
add a class that implements `AuthProvider` and select it with AUTH_PROVIDER.
"""

from dataclasses import dataclass
from typing import Protocol


class AuthError(Exception):
    """The token is missing, malformed, expired, or not signed by the provider. Maps to 401."""


class AuthUnavailableError(Exception):
    """The provider's signing keys or API could not be reached. Maps to 503 (fail closed)."""


@dataclass(frozen=True, slots=True)
class Identity:
    """Who the verified access token belongs to."""

    provider: str
    subject: str  # stable user id at the provider ("sub" claim)
    session_id: str | None = None  # "sid" claim, used to end a session
    organization_id: str | None = None
    # Only some providers put profile fields in the token (WorkOS does not).
    email: str | None = None
    # True only when the provider explicitly says it verified the email. ADMIN_EMAILS depends on this.
    email_verified: bool = False
    name: str | None = None
    picture: str | None = None


@dataclass(frozen=True, slots=True)
class Profile:
    """Profile data read from the provider by the backend itself, never from the frontend."""

    email: str | None
    email_verified: bool
    full_name: str | None
    avatar_url: str | None


class AuthProvider(Protocol):
    name: str

    def verify_access_token(self, token: str) -> Identity:
        """Verify signature, algorithm, issuer and expiry. Raises AuthError / AuthUnavailableError.

        Synchronous because key fetching may block; FastAPI runs it in a worker thread.
        """
        ...

    async def get_profile(self, identity: Identity) -> Profile: ...

    async def revoke_sessions(self, subject: str) -> int:
        """End every active session of the user at the provider. Returns how many were revoked."""
        ...

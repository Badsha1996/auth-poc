import logging

from app.auth.base import AuthError, Identity, Profile
from app.auth.jwt_verifier import JWTVerifier
from app.integrations.workos_client import WorkOSClient

logger = logging.getLogger("app.auth")


class WorkOSAuthProvider:
    """Verifies WorkOS AuthKit access tokens and reads profiles from the WorkOS API.

    Access tokens are RS256 JWTs signed with the keys at /sso/jwks/{client_id}. Their issuer is
    {api}/user_management/{client_id}. They carry sub (user id) and sid (session id), but no email,
    so the profile is fetched from WorkOS with the API key instead of trusting the frontend.
    """

    name = "workos"

    def __init__(self, *, client_id: str, issuer: str, client: WorkOSClient, api_base_url: str, leeway: int):
        self._client = client
        self._client_id = client_id
        self._verifier = JWTVerifier(
            jwks_url=f"{api_base_url}/sso/jwks/{client_id}",
            algorithms=["RS256"],
            issuer=issuer,
            required_claims=("exp", "iat", "iss", "sub", "sid"),
            leeway_seconds=leeway,
        )

    @property
    def api(self) -> WorkOSClient:
        return self._client

    def verify_access_token(self, token: str) -> Identity:
        claims = self._verifier.decode(token)
        # WorkOS tokens have no "aud"; client_id plays that role. Reject tokens minted for another app.
        if claims.get("client_id") != self._client_id:
            raise AuthError("Token was issued for a different WorkOS client")
        return Identity(
            provider=self.name,
            subject=claims["sub"],
            session_id=claims.get("sid"),
            organization_id=claims.get("org_id"),
        )

    async def get_profile(self, identity: Identity) -> Profile:
        user = await self._client.get_user(identity.subject)
        names = [user.get("first_name"), user.get("last_name")]
        full_name = " ".join(n for n in names if n) or user.get("name") or None
        return Profile(
            email=user.get("email"),
            email_verified=bool(user.get("email_verified")),
            full_name=full_name,
            avatar_url=user.get("profile_picture_url"),
        )

    async def revoke_sessions(self, subject: str) -> int:
        sessions = await self._client.list_sessions(subject)
        revoked = 0
        for session in sessions:
            if session.get("status") == "active":
                await self._client.revoke_session(session["id"])
                revoked += 1
        logger.info("revoked %s WorkOS session(s) for %s", revoked, subject)
        return revoked

from typing import Any

from app.auth.base import Identity, Profile
from app.auth.jwt_verifier import JWTVerifier


def _email_verified(claims: dict[str, Any]) -> bool:
    # Only an explicit boolean true counts. A token that merely carries an email proves nothing: without
    # this, an unverified sign-up using an ADMIN_EMAILS address would be made admin.
    # "email_verified" is the OIDC name; Better Auth's user field is "emailVerified".
    return claims.get("email_verified") is True or claims.get("emailVerified") is True


class GenericJWTProvider:
    """Any provider that issues signed JWTs (JWKS or HS256).

    Profile fields come from the verified token's claims. BetterAuthProvider builds on this class.
    """

    name = "jwt"

    def __init__(self, verifier: JWTVerifier) -> None:
        self._verifier = verifier

    def verify_access_token(self, token: str) -> Identity:
        claims = self._verifier.decode(token)
        return Identity(
            provider=self.name,
            subject=str(claims["sub"]),
            session_id=claims.get("sid"),
            organization_id=claims.get("org_id"),
            email=claims.get("email"),
            email_verified=_email_verified(claims),
            name=claims.get("name"),
            picture=claims.get("picture") or claims.get("image"),
        )

    async def get_profile(self, identity: Identity) -> Profile:
        return Profile(
            email=identity.email,
            email_verified=identity.email_verified,
            full_name=identity.name,
            avatar_url=identity.picture,
        )

    async def revoke_sessions(self, subject: str) -> int:
        # Plain JWT providers have no session API we can call; deactivation in our DB still blocks every
        # API call immediately, and the frontend shows the account as suspended.
        return 0

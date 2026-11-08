from app.auth.generic_jwt import GenericJWTProvider
from app.auth.jwt_verifier import JWTVerifier


class BetterAuthProvider(GenericJWTProvider):
    """Verifies JWTs minted by Better Auth's JWT plugin inside the Next.js app.

    The Next.js app (lib/auth/better-auth/server.ts) signs with EdDSA and sets issuer and audience to
    BETTER_AUTH_URL; this class expects exactly that. Its public keys are served at /api/auth/jwks.
    Profile fields (email, emailVerified, name, image) are in the token, so no extra API call is needed.
    """

    name = "better-auth"

    def __init__(self, *, base_url: str, leeway: int) -> None:
        base_url = base_url.rstrip("/")
        super().__init__(
            JWTVerifier(
                jwks_url=f"{base_url}/api/auth/jwks",
                algorithms=["EdDSA"],
                issuer=base_url,
                audience=base_url,
                required_claims=("exp", "iat", "iss", "aud", "sub"),
                leeway_seconds=leeway,
            )
        )

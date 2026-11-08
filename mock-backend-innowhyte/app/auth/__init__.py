from functools import lru_cache

from app.auth.base import AuthError, AuthProvider, AuthUnavailableError, Identity, Profile
from app.auth.better_auth import BetterAuthProvider
from app.auth.generic_jwt import GenericJWTProvider
from app.auth.jwt_verifier import JWTVerifier
from app.auth.workos import WorkOSAuthProvider
from app.core.config import settings
from app.integrations.workos_client import WorkOSClient


@lru_cache
def get_workos_client() -> WorkOSClient | None:
    if not settings.WORKOS_API_KEY:
        return None
    return WorkOSClient(
        api_key=settings.WORKOS_API_KEY.get_secret_value(), base_url=settings.WORKOS_API_BASE_URL
    )


@lru_cache
def get_auth_provider() -> AuthProvider:
    if settings.AUTH_PROVIDER == "workos":
        client = get_workos_client()
        assert client is not None and settings.WORKOS_CLIENT_ID
        return WorkOSAuthProvider(
            client_id=settings.WORKOS_CLIENT_ID,
            issuer=settings.workos_issuer,
            client=client,
            api_base_url=settings.WORKOS_API_BASE_URL,
            leeway=settings.JWT_LEEWAY_SECONDS,
        )
    if settings.AUTH_PROVIDER == "better-auth":
        assert settings.BETTER_AUTH_URL
        return BetterAuthProvider(base_url=settings.BETTER_AUTH_URL, leeway=settings.JWT_LEEWAY_SECONDS)
    return GenericJWTProvider(
        JWTVerifier(
            jwks_url=settings.JWT_JWKS_URL,
            secret=settings.JWT_SECRET.get_secret_value() if settings.JWT_SECRET else None,
            algorithms=settings.JWT_ALGORITHMS,
            issuer=settings.JWT_ISSUER,
            audience=settings.JWT_AUDIENCE,
            leeway_seconds=settings.JWT_LEEWAY_SECONDS,
        )
    )


__all__ = [
    "AuthError",
    "AuthProvider",
    "AuthUnavailableError",
    "Identity",
    "Profile",
    "get_auth_provider",
    "get_workos_client",
]

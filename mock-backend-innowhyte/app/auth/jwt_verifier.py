from collections.abc import Sequence
from typing import Any

import jwt

from app.auth.base import AuthError, AuthUnavailableError

_ASYMMETRIC_PREFIXES = ("RS", "PS", "ES", "Ed")


class JWTVerifier:
    """Strict JWT verification shared by all providers.

    - The algorithm list is pinned by configuration; the token header cannot choose it ("alg": "none"
      and RS256/HS256 key-confusion tricks are rejected).
    - exp/iat (and any extra required claims) must be present; exp is enforced with a small leeway.
    - issuer and audience are checked whenever they are configured.
    - JWKS keys are cached, and refetched automatically when the provider rotates to a new key id.
    """

    def __init__(
        self,
        *,
        algorithms: Sequence[str],
        jwks_url: str | None = None,
        secret: str | None = None,
        issuer: str | None = None,
        audience: str | None = None,
        required_claims: Sequence[str] = ("exp", "iat", "sub"),
        leeway_seconds: int = 10,
    ) -> None:
        if not (jwks_url or secret):
            raise ValueError("JWTVerifier needs a jwks_url or a secret")
        if jwks_url and any(not a.startswith(_ASYMMETRIC_PREFIXES) for a in algorithms):
            raise ValueError("JWKS verification only allows asymmetric algorithms")
        self._algorithms = list(algorithms)
        self._secret = secret
        self._issuer = issuer
        self._audience = audience
        self._required = list(required_claims)
        self._leeway = leeway_seconds
        self._jwks = (
            jwt.PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300, timeout=5) if jwks_url else None
        )

    def _signing_key(self, token: str) -> Any:
        if self._jwks is None:
            return self._secret
        try:
            return self._jwks.get_signing_key_from_jwt(token).key
        except jwt.PyJWKClientConnectionError as exc:
            raise AuthUnavailableError("Could not fetch signing keys") from exc

    def decode(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                key=self._signing_key(token),
                algorithms=self._algorithms,
                issuer=self._issuer,
                audience=self._audience,
                leeway=self._leeway,
                options={
                    "require": self._required,
                    "verify_aud": self._audience is not None,
                    "verify_iss": self._issuer is not None,
                },
            )
        except AuthUnavailableError:
            raise
        except jwt.PyJWTError as exc:
            raise AuthError(str(exc)) from exc

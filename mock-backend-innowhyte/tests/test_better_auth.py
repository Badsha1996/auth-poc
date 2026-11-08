"""Better Auth (EdDSA) token verification and the email-verified rule shared by JWT providers.

No network: the JWKS lookup is replaced with the test key.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from app.auth.base import AuthError
from app.auth.better_auth import BetterAuthProvider
from app.auth.generic_jwt import GenericJWTProvider
from app.auth.jwt_verifier import JWTVerifier

BASE_URL = "http://localhost:3000"

_private = ed25519.Ed25519PrivateKey.generate()
_public = _private.public_key()
_other_private = ed25519.Ed25519PrivateKey.generate()


def _claims(**overrides):
    now = int(time.time())
    claims = {
        "iss": BASE_URL,
        "aud": BASE_URL,
        "sub": "ba_user_1",
        "sid": "ba_session_1",
        "email": "person@example.com",
        "emailVerified": True,
        "name": "Pat Example",
        "image": "https://example.com/pat.png",
        "iat": now,
        "exp": now + 900,
    }
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


def _eddsa(claims, key=_private):
    return jwt.encode(claims, key, algorithm="EdDSA", headers={"kid": "ba_key"})


@pytest.fixture
def provider(monkeypatch):
    p = BetterAuthProvider(base_url=BASE_URL + "/", leeway=10)  # trailing slash is tolerated
    monkeypatch.setattr(p._verifier, "_signing_key", lambda _token: _public)
    return p


async def test_valid_better_auth_token(provider):
    identity = provider.verify_access_token(_eddsa(_claims()))
    assert identity.provider == "better-auth"  # stored in users.auth_provider; must match the frontend
    assert identity.subject == "ba_user_1"
    assert identity.session_id == "ba_session_1"
    assert identity.email_verified is True

    profile = await provider.get_profile(identity)
    assert profile.email == "person@example.com"
    assert profile.email_verified is True
    assert profile.full_name == "Pat Example"
    assert profile.avatar_url == "https://example.com/pat.png"


async def test_unverified_email_is_reported_unverified(provider):
    identity = provider.verify_access_token(_eddsa(_claims(emailVerified=False)))
    assert (await provider.get_profile(identity)).email_verified is False


def test_jwks_url_is_derived_from_base_url():
    p = BetterAuthProvider(base_url="https://app.example.com/", leeway=10)
    assert p._verifier._jwks.uri == "https://app.example.com/api/auth/jwks"


@pytest.mark.parametrize(
    "claims",
    [
        _claims(iss="https://evil.example.com"),  # issued by another app
        _claims(aud="https://other.example.com"),  # meant for another audience
        _claims(aud=None),  # no audience at all
        _claims(exp=int(time.time()) - 120),  # expired beyond leeway
        _claims(sub=None),  # no subject
    ],
)
def test_rejects_bad_claims(provider, claims):
    with pytest.raises(AuthError):
        provider.verify_access_token(_eddsa(claims))


def test_rejects_token_signed_by_another_key(provider):
    with pytest.raises(AuthError):
        provider.verify_access_token(_eddsa(_claims(), key=_other_private))


def test_rejects_hs256_token(provider):
    token = jwt.encode(_claims(), "some-shared-secret-that-is-long-enough", algorithm="HS256")
    with pytest.raises(AuthError):
        provider.verify_access_token(token)


@pytest.mark.parametrize(
    ("extra", "expected"),
    [
        ({}, False),  # an email claim alone proves nothing
        ({"email_verified": True}, True),  # OIDC name
        ({"emailVerified": True}, True),  # Better Auth name
        ({"email_verified": "true"}, False),  # only a real boolean counts
        ({"email_verified": False}, False),
    ],
)
async def test_generic_provider_email_verified_rule(extra, expected):
    secret = "test-secret-that-is-long-enough-for-hs256"
    p = GenericJWTProvider(JWTVerifier(algorithms=["HS256"], secret=secret))
    now = int(time.time())
    claims = {"sub": "u1", "iat": now, "exp": now + 60, "email": "a@example.com", **extra}
    token = jwt.encode(claims, secret, algorithm="HS256")
    profile = await p.get_profile(p.verify_access_token(token))
    assert profile.email_verified is expected

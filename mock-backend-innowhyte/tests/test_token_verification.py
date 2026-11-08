"""Unit tests for WorkOS-style RS256 token verification (no network: the JWKS lookup is replaced)."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.base import AuthError
from app.auth.jwt_verifier import JWTVerifier
from app.auth.workos import WorkOSAuthProvider
from app.integrations.workos_client import WorkOSClient

CLIENT_ID = "client_TEST123"
ISSUER = f"https://api.workos.com/user_management/{CLIENT_ID}"

_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_public = _private.public_key()
_other_private = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _claims(**overrides):
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "sub": "user_ABC",
        "sid": "session_XYZ",
        "client_id": CLIENT_ID,
        "iat": now,
        "exp": now + 300,
    }
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


def _rs256(claims, key=_private):
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "sso_oidc_key"})


@pytest.fixture
def provider(monkeypatch):
    p = WorkOSAuthProvider(
        client_id=CLIENT_ID,
        issuer=ISSUER,
        client=WorkOSClient(api_key="sk_test", base_url="https://api.workos.com"),
        api_base_url="https://api.workos.com",
        leeway=10,
    )
    monkeypatch.setattr(p._verifier, "_signing_key", lambda _token: _public)
    return p


def test_valid_workos_token(provider):
    identity = provider.verify_access_token(_rs256(_claims(org_id="org_1")))
    assert identity.subject == "user_ABC"
    assert identity.session_id == "session_XYZ"
    assert identity.organization_id == "org_1"
    assert identity.provider == "workos"


@pytest.mark.parametrize(
    "claims",
    [
        _claims(iss="https://evil.example.com"),  # wrong issuer
        _claims(iss=None),  # missing issuer
        _claims(sid=None),  # missing session id
        _claims(exp=int(time.time()) - 120),  # expired beyond leeway
        _claims(iat=None),  # missing issued-at
        _claims(client_id="client_OTHER"),  # minted for another WorkOS app
        _claims(client_id=None),  # no client binding
    ],
)
def test_rejects_bad_claims(provider, claims):
    with pytest.raises(AuthError):
        provider.verify_access_token(_rs256(claims))


def test_rejects_token_signed_by_another_key(provider):
    with pytest.raises(AuthError):
        provider.verify_access_token(_rs256(_claims(), key=_other_private))


def test_rejects_alg_none(provider):
    token = jwt.encode(_claims(), key=None, algorithm="none")
    with pytest.raises(AuthError):
        provider.verify_access_token(token)


def test_rejects_hs256_key_confusion(provider):
    # Classic attack: sign HS256 with the public key as the "secret". Pinned RS256 must reject it.
    pem = _public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    header = jwt.utils.base64url_encode(b'{"alg":"HS256","typ":"JWT"}')
    import hashlib
    import hmac
    import json

    body = jwt.utils.base64url_encode(json.dumps(_claims()).encode())
    sig = jwt.utils.base64url_encode(hmac.new(pem, header + b"." + body, hashlib.sha256).digest())
    with pytest.raises(AuthError):
        provider.verify_access_token((header + b"." + body + b"." + sig).decode())


def test_jwks_verifier_refuses_symmetric_algorithms():
    with pytest.raises(ValueError):
        JWTVerifier(jwks_url="https://example.com/jwks", algorithms=["HS256"])

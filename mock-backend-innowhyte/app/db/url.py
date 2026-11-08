"""Turn a libpq-style Postgres URL (what Neon, Prisma and psql use) into asyncpg engine arguments."""

import ssl
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

# libpq query parameters asyncpg does not accept as keyword arguments.
_LIBPQ_ONLY_PARAMS = {"sslmode", "channel_binding", "sslrootcert", "sslcert", "sslkey", "connect_timeout"}
_VERIFYING_SSL_MODES = {"require", "verify-ca", "verify-full"}


def asyncpg_engine_args(url: str) -> tuple[str, dict[str, Any]]:
    """Return (sqlalchemy_url, connect_args) for create_async_engine.

    sslmode=require/verify-* becomes a TLS context that verifies the server certificate and hostname,
    which is stricter than libpq's `require`. channel_binding has no asyncpg equivalent; the verified
    TLS connection gives the same man-in-the-middle protection.
    """
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query))
    sslmode = query.get("sslmode")
    kept = {k: v for k, v in query.items() if k not in _LIBPQ_ONLY_PARAMS}

    connect_args: dict[str, Any] = {}
    if sslmode in _VERIFYING_SSL_MODES:
        connect_args["ssl"] = ssl.create_default_context()
    elif sslmode == "prefer":
        connect_args["ssl"] = "prefer"

    sqlalchemy_url = urlunsplit(("postgresql+asyncpg", parts.netloc, parts.path, urlencode(kept), ""))
    return sqlalchemy_url, connect_args

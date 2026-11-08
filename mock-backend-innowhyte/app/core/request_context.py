from dataclasses import dataclass

from fastapi import Request


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Who/where a request came from, recorded on every audit event."""

    ip_address: str | None
    user_agent: str | None
    request_id: str | None


def get_request_context(request: Request) -> RequestContext:
    # request.client is the real client IP only when uvicorn trusts the proxy that set X-Forwarded-For
    # (--forwarded-allow-ips). Untrusted callers cannot spoof it.
    return RequestContext(
        ip_address=request.client.host if request.client else None,
        user_agent=(request.headers.get("user-agent") or "")[:512] or None,
        request_id=getattr(request.state, "request_id", None),
    )

"""Rate limiting (slowapi), keyed by client IP.

Storage is in-process memory: correct for a single API instance. When scaling the API
horizontally, point ``RATE_LIMIT_STORAGE_URI`` at a shared store (documented in DEPLOYMENT.md).
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.errors import error_response

_settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[_settings.rate_limit_default],
    enabled=_settings.rate_limit_enabled,
    headers_enabled=False,
)

AUTH_LIMIT = _settings.rate_limit_auth


def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return error_response(
        request,
        429,
        "rate_limited",
        "Too many requests, please slow down",
        details={"limit": str(exc.detail)},
        headers={"Retry-After": "60"},
    )

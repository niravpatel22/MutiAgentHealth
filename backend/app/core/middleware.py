"""ASGI middleware: request ids, security headers, request size and content-type guards.

Implemented as pure ASGI middleware (not BaseHTTPMiddleware) so they are cheap and do not
interfere with streaming responses or exception handling.
"""

import json
import re
import secrets
import time
import uuid

import structlog
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.logging import get_logger

log = get_logger("http")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")

# API responses are JSON only: nothing may load, frame, or execute.
API_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"


def docs_csp(nonce: str) -> str:
    """CSP for the Swagger UI page: scripts only via nonce or the pinned CDN, no inline eval."""
    return (
        "default-src 'none'; "
        f"script-src 'nonce-{nonce}' https://cdn.jsdelivr.net; "
        "style-src https://cdn.jsdelivr.net 'unsafe-inline'; "
        "img-src 'self' data: https://fastapi.tiangolo.com; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
    )


def _json_error(status: int, code: str, message: str, request_id: str | None) -> tuple[int, bytes]:
    body = {"error": {"code": code, "message": message, "details": None, "request_id": request_id}}
    return status, json.dumps(body).encode()


async def _send_json(
    send: Send, status: int, body: bytes, extra: list[tuple[bytes, bytes]]
) -> None:
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                *extra,
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})


class RequestContextMiddleware:
    """Assigns a request id, binds it to logs, echoes it back, and logs one line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()
        status_holder = {"status": 500}

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            # Path only (no query string): query params could carry identifiers.
            log.info(
                "request",
                method=scope["method"],
                path=scope["path"],
                status=status_holder["status"],
                duration_ms=round((time.perf_counter() - started) * 1000, 1),
            )
            structlog.contextvars.unbind_contextvars("request_id")


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, hsts: bool = True) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                present = {k.lower() for k, _ in headers}
                if b"content-security-policy" not in present:
                    headers.append((b"content-security-policy", API_CSP.encode()))
                headers += [
                    (b"x-content-type-options", b"nosniff"),
                    (b"referrer-policy", b"no-referrer"),
                    (b"x-frame-options", b"DENY"),
                    (b"cross-origin-opener-policy", b"same-origin"),
                    (b"cross-origin-resource-policy", b"cross-origin"),
                    (b"permissions-policy", b"camera=(), microphone=(), geolocation=()"),
                ]
                if b"cache-control" not in present:
                    headers.append((b"cache-control", b"no-store"))
                if self.hsts:
                    headers.append(
                        (b"strict-transport-security", b"max-age=63072000; includeSubDomains")
                    )
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


_BODY_METHODS = {"POST", "PUT", "PATCH"}
_ALLOWED_CONTENT_TYPES = ("application/json", "multipart/form-data")


class RequestGuardMiddleware:
    """Rejects oversized bodies (413) and unexpected content types (415) before routing."""

    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in _BODY_METHODS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        request_id = scope.get("state", {}).get("request_id")
        length = headers.get(b"content-length")
        if length is not None:
            try:
                too_big = int(length) > self.max_bytes
            except ValueError:
                too_big = True
            if too_big:
                status, body = _json_error(
                    413, "payload_too_large", "Request body too large", request_id
                )
                await _send_json(send, status, body, [])
                return

        ctype = headers.get(b"content-type", b"").decode("latin-1").lower()
        has_body = length not in (None, b"0") or b"transfer-encoding" in headers
        if has_body and not ctype.startswith(_ALLOWED_CONTENT_TYPES):
            status, body = _json_error(
                415, "unsupported_media_type", "Content-Type must be application/json", request_id
            )
            await _send_json(send, status, body, [])
            return

        # Enforce the limit on the actual stream too (chunked bodies have no content-length).
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise _BodyTooLargeError
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _BodyTooLargeError:
            status, body = _json_error(
                413, "payload_too_large", "Request body too large", request_id
            )
            await _send_json(send, status, body, [])


class _BodyTooLargeError(Exception):
    pass


def new_nonce() -> str:
    return secrets.token_urlsafe(16)

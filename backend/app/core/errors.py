"""Application errors and the single error envelope.

Every error response has the shape::

    {"error": {"code": "...", "message": "...", "details": ..., "request_id": "..."}}

Stack traces are never returned to clients; unexpected errors are logged with the request id.
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger

log = get_logger(__name__)


class AppError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"

    def __init__(
        self,
        message: str,
        *,
        details: Any = None,
        code: str | None = None,
        status_code: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.headers = headers
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


_STATUS_CODES = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    422: "validation_error",
    429: "rate_limited",
}


def request_id_of(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": request_id_of(request),
            }
        },
        headers=headers,
    )


def _clean_validation_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    # Never echo submitted values back (they may contain passwords).
    return [
        {"loc": list(err.get("loc", ())), "msg": err.get("msg", ""), "type": err.get("type", "")}
        for err in exc.errors()
    ]


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return error_response(
            request, exc.status_code, exc.code, exc.message, exc.details, exc.headers
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "error")
        message = exc.detail if isinstance(exc.detail, str) else code.replace("_", " ")
        return error_response(
            request, exc.status_code, code, message, headers=getattr(exc, "headers", None)
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(
            request,
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "validation_error",
            "Request validation failed",
            _clean_validation_errors(exc),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.error(
            "unhandled_exception",
            error_type=type(exc).__name__,
            path=request.url.path,
            request_id=request_id_of(request),
            exc_info=exc,
        )
        return error_response(
            request,
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "An unexpected error occurred",
        )

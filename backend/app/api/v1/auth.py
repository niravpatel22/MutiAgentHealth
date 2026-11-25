"""Authentication: register, login, refresh (rotating cookie), logout, me."""

from datetime import datetime

from fastapi import APIRouter, Request, Response, status

from app.api.deps import AppSettings, CurrentUser, DbSession, refresh_cookie
from app.core.config import Settings
from app.core.errors import ForbiddenError
from app.core.rate_limit import AUTH_LIMIT, limiter
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from app.schemas.common import error_responses
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _cookie_path(settings: Settings) -> str:
    return f"{settings.api_v1_prefix}/auth"


def _set_refresh_cookie(
    response: Response, settings: Settings, token: str, expires_at: datetime
) -> None:
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        expires=expires_at,
        path=_cookie_path(settings),
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=_cookie_path(settings),
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )


def _check_origin(request: Request, settings: Settings) -> None:
    """Defense in depth for cookie-authenticated endpoints (on top of SameSite=Strict)."""
    origin = request.headers.get("origin")
    if origin is not None and not settings.is_origin_allowed(origin):
        raise ForbiddenError("Origin not allowed")


def _token_response(issued: auth_service.IssuedTokens) -> TokenResponse:
    return TokenResponse(
        access_token=issued.access_token,
        expires_in=issued.expires_in,
        user=UserOut.model_validate(issued.user),
    )


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
    description=(
        "Creates a **manager** account. Passwords must be 12-128 characters, not a common or "
        "breached password, and not contain the email name. The first admin is seeded from "
        "environment variables, never through this endpoint."
    ),
    responses=error_responses(409, 422, 429),
)
@limiter.limit(AUTH_LIMIT)
def register(request: Request, body: RegisterRequest, db: DbSession) -> UserOut:
    user = auth_service.register_user(db, body.email, body.password)
    return UserOut.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Sign in",
    description=(
        "Returns a 15-minute access token in the body and sets a rotating refresh token in an "
        "`httpOnly`, `Secure`, `SameSite=Strict` cookie scoped to `/api/v1/auth`. "
        "Errors are deliberately generic."
    ),
    responses=error_responses(401, 422, 429),
)
@limiter.limit(AUTH_LIMIT)
def login(
    request: Request, response: Response, body: LoginRequest, db: DbSession, settings: AppSettings
) -> TokenResponse:
    issued = auth_service.login(db, settings, body.email, body.password)
    _set_refresh_cookie(response, settings, issued.refresh_token, issued.refresh_expires_at)
    return _token_response(issued)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Rotate the refresh token",
    description=(
        "Exchanges the refresh cookie for a new access token and a new refresh cookie. "
        "Re-using an already-rotated refresh token revokes the entire session family."
    ),
    responses=error_responses(401, 403, 429),
)
@limiter.limit(AUTH_LIMIT)
def refresh(
    request: Request, response: Response, db: DbSession, settings: AppSettings
) -> TokenResponse:
    _check_origin(request, settings)
    try:
        issued = auth_service.rotate_refresh(db, settings, refresh_cookie(request, settings))
    except Exception:
        _clear_refresh_cookie(response, settings)
        raise
    _set_refresh_cookie(response, settings, issued.refresh_token, issued.refresh_expires_at)
    return _token_response(issued)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Sign out",
    description="Revokes the refresh-token family server-side and clears the cookie.",
    responses=error_responses(403, 429),
)
@limiter.limit(AUTH_LIMIT)
def logout(request: Request, db: DbSession, settings: AppSettings) -> Response:
    _check_origin(request, settings)
    auth_service.logout(db, refresh_cookie(request, settings))
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_refresh_cookie(response, settings)
    return response


@router.get(
    "/me",
    response_model=UserOut,
    summary="Current user",
    responses=error_responses(401),
)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)

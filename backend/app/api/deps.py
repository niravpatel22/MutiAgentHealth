"""FastAPI dependencies: database session, current user, role guards, object-level access.

Authorization is always enforced here on the server, never only in the UI. Roles are re-read
from the database on every request, so demotion/deactivation takes effect immediately.
"""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import TokenError, decode_access_token
from app.db.models import Role, User
from app.db.session import get_db

_bearer = HTTPBearer(auto_error=False, description="Access token from /auth/login or /auth/refresh")

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def get_current_user(
    db: DbSession,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> User:
    challenge = {"WWW-Authenticate": "Bearer"}
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Not authenticated", headers=challenge)
    try:
        claims = decode_access_token(settings, credentials.credentials)
    except TokenError as exc:
        raise UnauthorizedError("Invalid or expired access token", headers=challenge) from exc
    user = db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("Invalid or expired access token", headers=challenge)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[User], User]:
    allowed = set(roles)

    def _guard(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise ForbiddenError("Your role does not allow this action")
        return user

    return _guard


AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]
ManagerOrAdmin = Annotated[User, Depends(require_roles(Role.ADMIN, Role.MANAGER))]


def ensure_owner_or_admin(user: User, owner_id: uuid.UUID, resource: str = "Resource") -> None:
    """Object-level authorization. Non-owners get 404 (not 403) to avoid leaking existence."""
    if user.role == Role.ADMIN or user.id == owner_id:
        return
    raise NotFoundError(f"{resource} not found")


def refresh_cookie(request: Request, settings: AppSettings) -> str | None:
    return request.cookies.get(settings.refresh_cookie_name)

"""Admin: user management. (All-analyses and all-reports views arrive with those modules.)"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import AdminUser, DbSession
from app.schemas.auth import AdminUserUpdate, UserOut
from app.schemas.common import Page, PageParams, error_responses
from app.services import user_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/users",
    response_model=Page[UserOut],
    summary="List users (admin)",
    responses=error_responses(401, 403),
)
def list_users(
    _admin: AdminUser, db: DbSession, page: Annotated[PageParams, Depends()]
) -> Page[UserOut]:
    users, total = user_service.list_users(db, page)
    return Page[UserOut](
        items=[UserOut.model_validate(u) for u in users],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.patch(
    "/users/{user_id}",
    response_model=UserOut,
    summary="Change a user's role or active flag (admin)",
    description="Deactivating a user revokes all of their sessions. Admins cannot lock themselves out.",
    responses=error_responses(400, 401, 403, 404, 422),
)
def update_user(
    user_id: uuid.UUID, body: AdminUserUpdate, admin: AdminUser, db: DbSession
) -> UserOut:
    return UserOut.model_validate(user_service.update_user(db, admin, user_id, body))

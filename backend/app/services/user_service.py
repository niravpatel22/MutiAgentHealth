"""User administration and business profiles."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError, NotFoundError
from app.db.base import utcnow
from app.db.models import BusinessProfile, Role, User
from app.schemas.auth import AdminUserUpdate, BusinessProfileIn
from app.schemas.common import PageParams
from app.services.auth_service import revoke_all_for_user


def list_users(db: Session, page: PageParams) -> tuple[list[User], int]:
    total = db.scalar(select(func.count()).select_from(User)) or 0
    users = db.scalars(
        select(User).order_by(User.created_at.desc()).offset(page.offset).limit(page.page_size)
    ).all()
    return list(users), total


def update_user(db: Session, actor: User, user_id: uuid.UUID, data: AdminUserUpdate) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    if user.id == actor.id and (
        (data.role is not None and data.role != Role.ADMIN) or data.is_active is False
    ):
        raise AppError(
            "Admins cannot demote or deactivate themselves", code="self_lockout", status_code=400
        )
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
        if not data.is_active:
            revoke_all_for_user(db, user.id)
    db.commit()
    db.refresh(user)
    return user


def get_profile(db: Session, user: User) -> BusinessProfile:
    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.user_id == user.id))
    if profile is None:
        raise NotFoundError("Business profile not set up yet")
    return profile


def upsert_profile(db: Session, user: User, data: BusinessProfileIn) -> BusinessProfile:
    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.user_id == user.id))
    if profile is None:
        profile = BusinessProfile(user_id=user.id, **data.model_dump())
        db.add(profile)
    else:
        for field, value in data.model_dump().items():
            setattr(profile, field, value)
        profile.updated_at = utcnow()
    db.commit()
    db.refresh(profile)
    return profile

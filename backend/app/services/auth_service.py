"""Authentication business logic: registration, login, refresh rotation, logout, admin seed.

No HTTP concerns live here; routers translate results into responses and cookies.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pydantic import EmailStr, TypeAdapter
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError, ConflictError, UnauthorizedError
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    new_refresh_token,
    password_problems,
    verify_password,
)
from app.db.models import RefreshToken, Role, User

log = get_logger(__name__)

INVALID_CREDENTIALS = "Invalid email or password"
INVALID_SESSION = "Session expired or invalid, please sign in again"


@dataclass(frozen=True)
class IssuedTokens:
    user: User
    access_token: str
    expires_in: int
    refresh_token: str
    refresh_expires_at: datetime


class WeakPasswordError(AppError):
    status_code = 422
    code = "weak_password"


def _now() -> datetime:
    return datetime.now(UTC)


def validate_password_or_raise(password: str, email: str) -> None:
    problems = password_problems(password, email)
    if problems:
        raise WeakPasswordError("Password does not meet the policy", details={"password": problems})


def register_user(db: Session, email: str, password: str, role: Role = Role.MANAGER) -> User:
    validate_password_or_raise(password, email)
    user = User(email=email, password_hash=hash_password(password), role=role, is_active=True)
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError("An account with this email already exists") from exc
    db.refresh(user)
    log.info("user_registered", user_id=str(user.id), role=user.role.value)
    return user


def _issue(
    db: Session, settings: Settings, user: User, family_id: uuid.UUID
) -> tuple[IssuedTokens, RefreshToken]:
    access, expires_in = create_access_token(settings, user.id, user.role.value)
    raw_refresh = new_refresh_token()
    expires_at = _now() + timedelta(days=settings.refresh_token_ttl_days)
    record = RefreshToken(
        user_id=user.id,
        family_id=family_id,
        token_hash=hash_refresh_token(raw_refresh),
        expires_at=expires_at,
    )
    db.add(record)
    db.flush()
    return IssuedTokens(user, access, expires_in, raw_refresh, expires_at), record


def login(db: Session, settings: Settings, email: str, password: str) -> IssuedTokens:
    user = db.scalar(select(User).where(User.email == email))
    # verify_password always runs argon2 (dummy hash for unknown users): no timing oracle.
    ok = verify_password(password, user.password_hash if user else None)
    if not ok or user is None or not user.is_active:
        log.info("login_failed")
        raise UnauthorizedError(INVALID_CREDENTIALS)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    issued, _ = _issue(db, settings, user, family_id=uuid.uuid4())
    db.commit()
    log.info("login_succeeded", user_id=str(user.id))
    return issued


def revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def revoke_all_for_user(db: Session, user_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def rotate_refresh(db: Session, settings: Settings, raw_token: str | None) -> IssuedTokens:
    """Exchange a refresh token for a new pair. Reusing a rotated token revokes its family."""
    if not raw_token:
        raise UnauthorizedError(INVALID_SESSION)
    record = db.scalar(
        select(RefreshToken)
        .where(RefreshToken.token_hash == hash_refresh_token(raw_token))
        .with_for_update()
    )
    if record is None:
        raise UnauthorizedError(INVALID_SESSION)

    if record.revoked_at is not None:
        # Token already used or revoked: possible theft. Kill the whole family.
        revoke_family(db, record.family_id)
        db.commit()
        log.warning("refresh_token_reuse_detected", user_id=str(record.user_id))
        raise UnauthorizedError(INVALID_SESSION)

    user = db.get(User, record.user_id)
    expires_at = (
        record.expires_at
        if record.expires_at.tzinfo is not None
        else record.expires_at.replace(tzinfo=UTC)
    )
    if expires_at <= _now() or user is None or not user.is_active:
        record.revoked_at = _now()
        db.commit()
        raise UnauthorizedError(INVALID_SESSION)

    issued, new_record = _issue(db, settings, user, family_id=record.family_id)
    record.revoked_at = _now()
    record.replaced_by_id = new_record.id
    db.commit()
    return issued


def logout(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    record = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw_token))
    )
    if record is not None:
        revoke_family(db, record.family_id)
        db.commit()
        log.info("logout", user_id=str(record.user_id))


def seed_admin(db: Session, settings: Settings) -> tuple[User, bool]:
    """Create the first admin from env vars. Idempotent; returns (user, created)."""
    raw_email = settings.admin_email.strip().lower()
    password = settings.admin_password.get_secret_value()
    if not raw_email or not password:
        raise ValueError("ADMIN_EMAIL and ADMIN_PASSWORD must be set to seed the admin")
    email = str(TypeAdapter(EmailStr).validate_python(raw_email)).lower()
    existing = db.scalar(select(User).where(User.email == email))
    if existing is not None:
        if existing.role != Role.ADMIN:
            existing.role = Role.ADMIN
            db.commit()
        return existing, False
    return register_user(db, email, password, role=Role.ADMIN), True

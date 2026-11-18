"""Password hashing/policy, JWT access tokens, and opaque refresh tokens.

- Passwords: argon2id (argon2-cffi defaults follow RFC 9106 recommendations); verification is
  constant-time inside argon2. Policy: 12..128 chars, not a common/breached password, not built
  from the user's email, not trivially repetitive or sequential.
- Access tokens: HS256 JWT with explicit ``iss``/``aud``/``exp``/``iat``/``sub``/``jti``/``typ``.
  Decoding pins the algorithm list and requires every claim.
- Refresh tokens: 256-bit random strings; only their SHA-256 digest is stored server-side.
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from importlib import resources

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import Settings

PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 128

_hasher = PasswordHasher()  # argon2id
# Pre-computed hash used to equalise timing when the user does not exist.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(32))


# ----------------------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Constant-time verify. Always performs one argon2 verification, even for unknown users."""
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


@lru_cache
def _common_passwords() -> frozenset[str]:
    text = resources.files("app.core").joinpath("data/common_passwords.txt").read_text("utf-8")
    return frozenset(line.strip().lower() for line in text.splitlines() if line.strip())


_SEQUENCES = ("abcdefghijklmnopqrstuvwxyz", "0123456789", "qwertyuiopasdfghjklzxcvbnm")


def _is_sequential(pw: str) -> bool:
    low = pw.lower()
    return any(low in seq or low in seq[::-1] for seq in _SEQUENCES)


def password_problems(password: str, email: str | None = None) -> list[str]:
    """Return human-readable policy violations (empty list = acceptable)."""
    problems: list[str] = []
    if len(password) < PASSWORD_MIN_LENGTH:
        problems.append(f"must be at least {PASSWORD_MIN_LENGTH} characters")
    if len(password) > PASSWORD_MAX_LENGTH:
        problems.append(f"must be at most {PASSWORD_MAX_LENGTH} characters")
    low = password.lower()
    if low in _common_passwords():
        problems.append("is too common (appears in breached-password lists)")
    if len(set(password)) <= 3:
        problems.append("is too repetitive")
    elif _is_sequential(password):
        problems.append("is a simple keyboard or character sequence")
    if email:
        local = email.split("@", 1)[0].lower()
        if len(local) >= 4 and local in low:
            problems.append("must not contain your email name")
    return problems


# ----------------------------------------------------------------------------- JWT
class TokenError(Exception):
    """Raised for any invalid, expired, or malformed token."""


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    jti: str


def create_access_token(settings: Settings, user_id: uuid.UUID, role: str) -> tuple[str, int]:
    now = datetime.now(UTC)
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    payload = {
        "sub": str(user_id),
        "role": role,  # informational for the UI; the server always re-reads the role from DB
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": secrets.token_hex(16),
        "typ": "access",
    }
    token = jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return token, int(ttl.total_seconds())


def decode_access_token(settings: Settings, token: str) -> AccessClaims:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub", "jti", "typ"]},
            leeway=5,
        )
        if payload.get("typ") != "access":
            raise TokenError("wrong token type")
        return AccessClaims(user_id=uuid.UUID(payload["sub"]), jti=payload["jti"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise TokenError(str(exc)) from exc


# ----------------------------------------------------------------------------- refresh tokens
def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

"""Unit tests for password hashing/policy, JWT claims, refresh hashes, and log redaction."""

import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.core.logging import REDACTED, redact_processor
from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    new_refresh_token,
    password_problems,
    verify_password,
)


def test_password_hash_and_verify_roundtrip() -> None:
    hashed = hash_password("Clinical-Ops-2026!")
    assert hashed.startswith("$argon2id$")
    assert verify_password("Clinical-Ops-2026!", hashed) is True
    assert verify_password("Wrong-Password-2026!", hashed) is False
    assert verify_password("Clinical-Ops-2026!", None) is False
    assert verify_password("Clinical-Ops-2026!", "not-a-valid-hash") is False
    assert needs_rehash(hashed) is False


def test_password_policy_rejects_weak_inputs() -> None:
    assert any("at least" in p for p in password_problems("short"))
    assert any("at most" in p for p in password_problems("x" * 130))
    assert any("common" in p for p in password_problems("password1234"))
    assert any("repetitive" in p for p in password_problems("aaaaaaaaaaaa"))
    assert any("sequence" in p for p in password_problems("abcdefghijkl"))
    assert any("email" in p for p in password_problems("alice_smith_2026!", "alice_smith@hosp.in"))
    assert password_problems("Sunrise#Ward99!Ops", "alice_smith@hosp.in") == []


def test_jwt_encode_decode_and_claim_validation(test_settings: Settings) -> None:
    uid = uuid.uuid4()
    token, ttl = create_access_token(test_settings, uid, "manager")
    assert ttl == 900
    claims = decode_access_token(test_settings, token)
    assert claims.user_id == uid
    assert len(claims.jti) == 32

    # Wrong audience
    wrong_aud = test_settings.model_copy(update={"jwt_audience": "other-aud"})
    with pytest.raises(TokenError):
        decode_access_token(wrong_aud, token)

    # Wrong issuer
    wrong_iss = test_settings.model_copy(update={"jwt_issuer": "other-iss"})
    with pytest.raises(TokenError):
        decode_access_token(wrong_iss, token)

    # Wrong token type
    now = int(datetime.now(UTC).timestamp())
    bad_type = jwt.encode(
        {
            "sub": str(uid),
            "iss": test_settings.jwt_issuer,
            "aud": test_settings.jwt_audience,
            "iat": now,
            "nbf": now,
            "exp": now + 60,
            "jti": "abc",
            "typ": "refresh",
        },
        test_settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    with pytest.raises(TokenError):
        decode_access_token(test_settings, bad_type)

    # Expired token
    expired = jwt.encode(
        {
            "sub": str(uid),
            "iss": test_settings.jwt_issuer,
            "aud": test_settings.jwt_audience,
            "iat": now - 120,
            "nbf": now - 120,
            "exp": int((datetime.now(UTC) - timedelta(seconds=30)).timestamp()),
            "jti": "abc",
            "typ": "access",
        },
        test_settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )
    with pytest.raises(TokenError):
        decode_access_token(test_settings, expired)


def test_refresh_token_generation_and_hashing() -> None:
    raw1 = new_refresh_token()
    raw2 = new_refresh_token()
    assert raw1 != raw2
    assert len(hash_refresh_token(raw1)) == 64
    assert hash_refresh_token(raw1) == hash_refresh_token(raw1)


def test_production_settings_require_strong_secret_and_secure_cookie() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, app_env="production", jwt_secret="short")
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            app_env="production",
            jwt_secret="a" * 40,
            cookie_secure=False,
        )


def test_log_redaction_strips_secrets_and_pii() -> None:
    event = {
        "event": "user_action",
        "password": "secret",
        "nested": {"access_token": "jwt", "patient_name": "Ramesh", "safe": 42},
        "items": [{"phone_number": "9876543210"}],
    }
    cleaned = redact_processor(None, "info", event)
    assert cleaned["password"] == REDACTED
    assert cleaned["nested"]["access_token"] == REDACTED
    assert cleaned["nested"]["patient_name"] == REDACTED
    assert cleaned["nested"]["safe"] == 42
    assert cleaned["items"][0]["phone_number"] == REDACTED

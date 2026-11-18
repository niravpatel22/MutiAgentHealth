"""RBAC matrix, object-level authorization (IDOR), business profile, admin, and middleware."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import ensure_owner_or_admin
from app.cli import main as cli_main
from app.core.config import Settings
from app.core.errors import ForbiddenError, NotFoundError
from app.db.models import Role, User
from app.services import auth_service


def _token_for(
    client: TestClient, email: str, password: str = "Sunrise#Ward99!Ops"  # noqa: S107
) -> str:
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_rbac_matrix_and_admin_user_lifecycle(
    client: TestClient, db_session: Session, test_settings: Settings
) -> None:
    admin_user, created = auth_service.seed_admin(db_session, test_settings)
    assert created is True
    # Idempotent second call
    _, created_again = auth_service.seed_admin(db_session, test_settings)
    assert created_again is False

    mgr = auth_service.register_user(
        db_session, "mgr@careops.example", "Sunrise#Ward99!Ops", role=Role.MANAGER
    )
    analyst = auth_service.register_user(
        db_session, "analyst@careops.example", "Sunrise#Ward99!Ops", role=Role.ANALYST
    )

    admin_tok = _token_for(client, admin_user.email, "Chief-Strong-Pass-99!")
    mgr_tok = _token_for(client, mgr.email)
    analyst_tok = _token_for(client, analyst.email)

    # /admin/users: unauthenticated -> 401, manager/analyst -> 403, admin -> 200
    assert client.get("/api/v1/admin/users").status_code == 401
    assert (
        client.get(
            "/api/v1/admin/users", headers={"Authorization": f"Bearer {mgr_tok}"}
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/admin/users", headers={"Authorization": f"Bearer {analyst_tok}"}
        ).status_code
        == 403
    )
    listing = client.get(
        "/api/v1/admin/users?page=1&page_size=10",
        headers={"Authorization": f"Bearer {admin_tok}"},
    )
    assert listing.status_code == 200
    assert listing.json()["total"] == 3

    # Admin cannot demote or deactivate themselves
    self_demote = client.patch(
        f"/api/v1/admin/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"role": "manager"},
    )
    assert self_demote.status_code == 400
    assert self_demote.json()["error"]["code"] == "self_lockout"

    # Admin deactivates manager -> manager's existing access token stops working immediately
    deact = client.patch(
        f"/api/v1/admin/users/{mgr.id}",
        headers={"Authorization": f"Bearer {admin_tok}"},
        json={"is_active": False},
    )
    assert deact.status_code == 200
    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {mgr_tok}"}).status_code
        == 401
    )


def test_business_profile_isolation_and_object_authorization(
    client: TestClient, db_session: Session
) -> None:
    u1 = auth_service.register_user(db_session, "u1@careops.example", "Sunrise#Ward99!Ops")
    u2 = auth_service.register_user(db_session, "u2@careops.example", "Sunrise#Ward99!Ops")
    admin = auth_service.register_user(
        db_session, "adm@careops.example", "Sunrise#Ward99!Ops", role=Role.ADMIN
    )
    t1 = _token_for(client, u1.email)
    t2 = _token_for(client, u2.email)

    # 404 before profile exists
    assert (
        client.get(
            "/api/v1/business-profile", headers={"Authorization": f"Bearer {t1}"}
        ).status_code
        == 404
    )

    # Create then update profile for u1; u2 still sees 404 (isolated per user)
    created = client.put(
        "/api/v1/business-profile",
        headers={"Authorization": f"Bearer {t1}"},
        json={
            "company_name": "Sunrise Hospital",
            "industry": "Healthcare",
            "team_size": 180,
            "business_goals": "Cut OPD wait times below 30 min",
        },
    )
    assert created.status_code == 200
    assert created.json()["company_name"] == "Sunrise Hospital"
    assert (
        client.get(
            "/api/v1/business-profile", headers={"Authorization": f"Bearer {t2}"}
        ).status_code
        == 404
    )

    updated = client.put(
        "/api/v1/business-profile",
        headers={"Authorization": f"Bearer {t1}"},
        json={
            "company_name": "Sunrise Multispeciality",
            "industry": "Healthcare",
            "team_size": 220,
            "business_goals": "Improve margin",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["team_size"] == 220
    assert updated.json()["updated_at"] is not None

    # Object-level helper: owner and admin pass, other user gets 404 (not 403, to prevent IDOR probing)
    ensure_owner_or_admin(u1, u1.id, "Dataset")
    ensure_owner_or_admin(admin, u1.id, "Dataset")
    try:
        ensure_owner_or_admin(u2, u1.id, "Dataset")
        raise AssertionError("Expected NotFoundError")
    except NotFoundError as exc:
        assert exc.status_code == 404
        assert not isinstance(exc, ForbiddenError)


def test_security_headers_request_guards_and_error_envelope(client: TestClient) -> None:
    res = client.get("/api/v1/health", headers={"X-Request-ID": "req-12345678"})
    assert res.headers["x-request-id"] == "req-12345678"
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["referrer-policy"] == "no-referrer"
    assert "max-age=" in res.headers["strict-transport-security"]
    assert "frame-ancestors 'none'" in res.headers["content-security-policy"]
    assert "unsafe-inline" not in res.headers["content-security-policy"]

    # Swagger UI sets a nonce-based script CSP (no unsafe-inline in script-src)
    docs = client.get("/docs")
    assert docs.status_code == 200
    csp = docs.headers["content-security-policy"]
    script_directive = next(d for d in csp.split(";") if "script-src" in d)
    assert "nonce-" in script_directive
    assert "unsafe-inline" not in script_directive

    # Unsupported Content-Type -> 415 envelope
    bad_ct = client.post(
        "/api/v1/auth/login", content="plain text", headers={"Content-Type": "text/plain"}
    )
    assert bad_ct.status_code == 415
    assert bad_ct.json()["error"]["code"] == "unsupported_media_type"

    # Validation errors never echo secret field values
    bad_val = client.post(
        "/api/v1/auth/login", json={"email": "not-an-email", "password": "MySecretValue!"}
    )
    assert bad_val.status_code == 422
    assert "MySecretValue!" not in bad_val.text


def test_cli_seed_admin(monkeypatch, db_session: Session, test_settings: Settings) -> None:
    monkeypatch.setattr("app.cli.get_settings", lambda: test_settings)
    monkeypatch.setattr("app.cli.get_sessionmaker", lambda: lambda: db_session)
    assert cli_main(["seed-admin"]) == 0
    seeded = db_session.query(User).filter_by(email="admin@careops.example").one()
    assert seeded.role == Role.ADMIN
    assert seeded.id != uuid.UUID(int=0)

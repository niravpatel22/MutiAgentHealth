"""End-to-end tests for /api/v1/auth/* flows, cookie attributes, rotation, and rate limits."""

from fastapi.testclient import TestClient


def test_register_login_me_refresh_and_logout_flow(client: TestClient) -> None:
    # Register normalizes email and assigns manager role
    reg = client.post(
        "/api/v1/auth/register",
        json={"email": "  Manager.One@Hospital.Example ", "password": "Sunrise#Ward99!Ops"},
    )
    assert reg.status_code == 201
    user = reg.json()
    assert user["email"] == "manager.one@hospital.example"
    assert user["role"] == "manager"
    assert user["is_active"] is True

    # Duplicate email returns 409 error envelope
    dup = client.post(
        "/api/v1/auth/register",
        json={"email": "manager.one@hospital.example", "password": "Sunrise#Ward99!Ops"},
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "conflict"

    # Login issues access token + httpOnly SameSite=strict Secure refresh cookie
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "MANAGER.ONE@hospital.example", "password": "Sunrise#Ward99!Ops"},
    )
    assert login.status_code == 200
    set_cookie = login.headers.get("set-cookie", "")
    assert "careops_refresh=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=strict" in set_cookie
    assert "Secure" in set_cookie
    assert "Path=/api/v1/auth" in set_cookie
    first_refresh = client.cookies.get("careops_refresh")
    access_token = login.json()["access_token"]

    # /me returns the signed-in user
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me.status_code == 200
    assert me.json()["id"] == user["id"]

    # /refresh rotates the cookie and returns a new access token
    refreshed = client.post("/api/v1/auth/refresh", headers={"Origin": "http://localhost:5173"})
    assert refreshed.status_code == 200
    second_refresh = client.cookies.get("careops_refresh")
    assert second_refresh != first_refresh

    # Re-presenting the old (already rotated) refresh token triggers reuse detection
    # and revokes the entire token family (including second_refresh).
    client.cookies.set("careops_refresh", first_refresh, path="/api/v1/auth")
    reuse = client.post("/api/v1/auth/refresh")
    assert reuse.status_code == 401

    client.cookies.set("careops_refresh", second_refresh, path="/api/v1/auth")
    after_compromise = client.post("/api/v1/auth/refresh")
    assert after_compromise.status_code == 401

    # Fresh login followed by logout revokes the session
    client.post(
        "/api/v1/auth/login",
        json={"email": "manager.one@hospital.example", "password": "Sunrise#Ward99!Ops"},
    )
    out = client.post("/api/v1/auth/logout", headers={"Origin": "http://localhost:5173"})
    assert out.status_code == 204
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_generic_login_errors_and_weak_password_validation(client: TestClient) -> None:
    # Weak password rejected with 422 and policy details
    weak = client.post(
        "/api/v1/auth/register",
        json={"email": "user@hospital.example", "password": "password1234"},
    )
    assert weak.status_code == 422
    assert weak.json()["error"]["code"] == "weak_password"

    # Unknown user and wrong password return identical 401 error messages
    unknown = client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@hospital.example", "password": "Sunrise#Ward99!Ops"},
    )
    client.post(
        "/api/v1/auth/register",
        json={"email": "real@hospital.example", "password": "Sunrise#Ward99!Ops"},
    )
    wrong = client.post(
        "/api/v1/auth/login",
        json={"email": "real@hospital.example", "password": "Wrong#Ward99!Ops"},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["error"]["message"] == wrong.json()["error"]["message"]


def test_origin_check_and_rate_limiting(client: TestClient) -> None:
    bad_origin = client.post("/api/v1/auth/refresh", headers={"Origin": "https://evil.example.com"})
    assert bad_origin.status_code == 403
    assert bad_origin.json()["error"]["code"] == "forbidden"

    # Exceed the 10/minute auth rate limit
    statuses = [
        client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@hospital.example", "password": "Sunrise#Ward99!Ops"},
        ).status_code
        for _ in range(11)
    ]
    assert 429 in statuses

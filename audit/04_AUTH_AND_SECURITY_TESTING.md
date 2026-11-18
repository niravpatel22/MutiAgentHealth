# Phase 4 — Authentication and Authorization Testing

**Project:** MediOps Intelligence — AI-Powered Hospital Operations & Performance Intelligence
**Audit Date:** 2026-11-18

---

## 1. Authentication Lifecycle Verification (11 Mandatory Scenarios)

| # | Lifecycle Scenario | Test Method & Input | Expected Outcome | Actual Outcome & Evidence | Status |
|---:|---|---|---|---|---|
| **1** | **Register a new user** | `POST /api/v1/auth/register` with `{"email":"  Manager.One@Hospital.Example ","password":"Sunrise#Ward99!Ops"}` | `201 Created`, email normalized to lowercase `manager.one@hospital.example`, assigned role `manager`, password hashed with `$argon2id$` | `201 Created`, `role="manager"`, `is_active=True`, `password_hash.startswith("$argon2id$")` (`test_register_login_me_refresh_and_logout_flow`, `test_password_hash_and_verify_roundtrip`) | **PASS** |
| **2** | **Login with valid credentials** | `POST /api/v1/auth/login` with registered email & password | `200 OK`, returns 15-min (`expires_in: 900`) `HS256` access JWT in JSON body + sets `careops_refresh` cookie (`HttpOnly; Secure; SameSite=strict; Path=/api/v1/auth`) | `200 OK`, verified `access_token` claims (`sub`, `iss`, `aud`, `iat`, `nbf`, `exp`, `jti`, `typ="access"`) and all cookie flags (`test_register_login_me_refresh_and_logout_flow`) | **PASS** |
| **3** | **Login with incorrect credentials** | `POST /api/v1/auth/login` with wrong password (`Wrong#Ward99!Ops`) or unknown email (`nobody@hospital.example`) | `401 Unauthorized` with identical generic message and constant-time Argon2 verification (dummy hash verified when email not found) | Both return `401 Unauthorized` with identical `error.message` (`test_generic_login_errors_and_weak_password_validation`) | **PASS** |
| **4** | **Access protected pages without login** | Navigate to `/dashboard`, `/datasets`, `/analyses`, `/reports`, `/approvals`, `/chat`, `/history`, `/admin` without an active session | `RequireAuth.jsx` attempts `/auth/refresh` once; when unauthenticated, redirects to `/login` (`<Navigate to="/login" replace />`) | Verified in `RequireAuth.jsx` and live browser testing (unauthenticated access redirects to `/login`) | **PASS** |
| **5** | **Access protected APIs without login** | `GET /api/v1/auth/me`, `GET /api/v1/datasets`, `GET /api/v1/admin/users` without `Authorization: Bearer` header | `401 Unauthorized` (`error.code == "unauthorized"`) | `401 Unauthorized` across all protected endpoints | **PASS** |
| **6** | **Refresh access token** | `POST /api/v1/auth/refresh` with valid `careops_refresh` cookie and `Origin: http://localhost:5173` | `200 OK`, issues a new 15-min access JWT and rotates the `careops_refresh` cookie (`second_refresh != first_refresh`) | `200 OK`, `second_refresh != first_refresh` (`test_register_login_me_refresh_and_logout_flow`) | **PASS** |
| **7** | **Logout** | `POST /api/v1/auth/logout` with active refresh cookie | `204 No Content`, revokes refresh token family in PostgreSQL and deletes `careops_refresh` cookie | `204 No Content`, subsequent `/api/v1/auth/refresh` returns `401 Unauthorized` | **PASS** |
| **8** | **Reuse a revoked / rotated refresh token** | Replay `first_refresh` after it was rotated to `second_refresh` | `401 Unauthorized` AND server revokes the entire token family (`family_id`) so `second_refresh` is also immediately invalidated | Both `first_refresh` replay and subsequent `second_refresh` call return `401 Unauthorized` (`test_register_login_me_refresh_and_logout_flow`) | **PASS** |
| **9** | **Use an expired access token** | Present a JWT signed with `exp = now - 30s` (or wrong `iss`, wrong `aud`, or `typ="refresh"`) | `decode_access_token` raises `TokenError` → `401 Unauthorized` | Verified in `test_jwt_encode_decode_and_claim_validation` | **PASS** |
| **10** | **Attempt access with a disabled account** | Admin patches user `is_active: false` (`PATCH /api/v1/admin/users/{id}`); user then calls `GET /api/v1/auth/me` with their still-unexpired access JWT | `401 Unauthorized` immediately (because `CurrentUser` dependency re-queries PostgreSQL `User.is_active` on every request and `update_user` revokes all refresh tokens) | `401 Unauthorized` immediately after deactivation (`test_rbac_matrix_and_admin_user_lifecycle`) | **PASS** |
| **11** | **Attempt unauthorized resource access (IDOR)** | Manager B attempts `GET`/`POST`/`DELETE` on Manager A's dataset, quality report, KPIs, trends, breakdowns, analysis, report, PDF, recommendation, or chat session | `404 Not Found` (deliberately returns `404` rather than `403` via `ensure_owner_or_admin` to prevent resource UUID enumeration) | Verified `404 Not Found` across all 10 resource types (`test_ingestion_and_metrics.py`, `test_analytics_api.py`, `test_crew_and_worker.py`, `test_reports_and_hitl.py`, `test_chat_and_admin.py`) | **PASS** |

---

## 2. Role-Based Access Control (RBAC) Matrix Verification

All three roles (`admin`, `manager`, `analyst`) are enforced server-side via FastAPI dependencies (`CurrentUser`, `ManagerOrAdmin`, `AdminUser`, and `ensure_owner_or_admin`):

| Operation / Endpoint | `admin` | `manager` (Owner) | `manager` (Non-Owner) | `analyst` | Unauthenticated | Verified Status |
|---|---|---|---|---|---|---|
| **View own/shared Dashboard, Reports, Recommendations, History, AI Chat** | `200 OK` (All) | `200 OK` (Own) | `404 Not Found` (IDOR) | `200 OK` (Permitted) | `401 Unauthorized` | **PASS** |
| **Upload Dataset (`POST /api/v1/datasets`)** | `201 Created` | `201 Created` | N/A | **`403 Forbidden`** | `401 Unauthorized` | **PASS** |
| **Delete Dataset (`DELETE /api/v1/datasets/{id}`)** | `204 No Content` | `204 No Content` | `404 Not Found` | **`403 Forbidden`** | `401 Unauthorized` | **PASS** |
| **Trigger AI Analysis (`POST /api/v1/analyses`)** | `202 Accepted` | `202 Accepted` | `404 Not Found` | **`403 Forbidden`** | `401 Unauthorized` | **PASS** |
| **Cancel AI Analysis (`POST /api/v1/analyses/{id}/cancel`)** | `200 OK` | `200 OK` | `404 Not Found` | **`403 Forbidden`** | `401 Unauthorized` | **PASS** |
| **Approve / Reject HITL Recommendation (`POST /api/v1/recommendations/{id}/decision`)** | `200 OK` | `200 OK` | `404 Not Found` | **`403 Forbidden`** | `401 Unauthorized` | **PASS** |
| **List / Update Users (`GET` & `PATCH /api/v1/admin/users`)** | `200 OK` (`400` on self-lockout) | **`403 Forbidden`** | **`403 Forbidden`** | **`403 Forbidden`** | `401 Unauthorized` | **PASS** |
| **Organization-Wide Audit Views (`GET /api/v1/admin/analyses` & `/reports`)** | `200 OK` | **`403 Forbidden`** | **`403 Forbidden`** | **`403 Forbidden`** | `401 Unauthorized` | **PASS** |

---

## 3. Cryptographic, Cookie, Token Storage & Header Controls

1. **Password Hashing (`argon2id`)**:
   - Uses `argon2-cffi` (`PasswordHasher()`), producing `$argon2id$v=19$m=65536,t=3,p=4$...` hashes.
   - Constant-time verification (`_DUMMY_HASH`) prevents user-enumeration timing attacks on `/api/v1/auth/login`.
   - Password policy enforces 12–128 characters, blocks common/breached passwords (`common_passwords.txt`), repetitive characters, sequences, and email local-part substrings.
2. **Secure Refresh Cookie & CSRF Protection**:
   - Refresh tokens are 256-bit cryptographically random tokens (`secrets.token_urlsafe(32)`), stored only as SHA-256 digests (`token_hash`) in PostgreSQL `refresh_tokens`.
   - Cookie attributes: `HttpOnly`, `Secure`, `SameSite=strict`, `Path=/api/v1/auth`.
   - Defense-in-depth `_check_origin` on `/api/v1/auth/refresh` and `/api/v1/auth/logout` rejects any request whose `Origin` header is not in `settings.cors_origins` (`403 Forbidden`).
3. **In-Memory Access Token Storage (Zero `localStorage` / `sessionStorage`)**:
   - Inspected `frontend/src/api/client.js`: `let accessToken = null;` is module-scoped in memory only. Neither `localStorage` nor `sessionStorage` is ever used to store JWTs.
4. **CORS & Security Headers (`SecurityHeadersMiddleware`)**:
   - `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'` on all API responses (and per-request cryptographic nonce `script-src 'nonce-...'` on `/docs`).
   - `Strict-Transport-Security: max-age=31536000; includeSubDomains`
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `Referrer-Policy: no-referrer`
   - `Permissions-Policy: geolocation=(), microphone=(), camera=()`

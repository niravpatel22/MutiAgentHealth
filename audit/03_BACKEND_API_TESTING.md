# Phase 3 — Backend and API Testing

**Project:** MediOps Intelligence — AI-Powered Hospital Operations & Performance Intelligence
**Base URL Tested:** `http://127.0.0.1:8000/api/v1` (plus `/docs` and `/openapi.json`)
**Swagger / OpenAPI Verification:** `GET /docs` (`200 OK`, nonce-CSP protected) and `GET /openapi.json` (`200 OK`, 29 documented operations across 10 tags)

---

## 1. Error Envelope, Validation & Global Middleware Verification

Every error response across the API was verified to return the standardized JSON envelope:
```json
{
  "error": {
    "code": "<machine_readable_code>",
    "message": "<human_readable_message>",
    "details": [...],
    "request_id": "<32-char_hex_or_caller_X-Request-ID>"
  }
}
```
- **Secret scrubbing in `422` validation errors:** Verified that invalid payloads containing `password` or `secret` fields never echo the submitted secret value in `error.details` (`test_security_headers_request_guards_and_error_envelope`: `assert "MySecretValue!" not in bad_val.text`).
- **Content-Type guard (`415`):** `POST` with `Content-Type: text/plain` returns `415 Unsupported Media Type` (`code: "unsupported_media_type"`).
- **Pagination boundary enforcement (`422`):** `GET /api/v1/datasets?page=0` and `GET /api/v1/datasets?page_size=500` return `422 Unprocessable Content` (`code: "validation_error"`).
- **Zero unhandled `500` errors or stack traces:** Confirmed across all positive, negative, boundary, unauthorized, forbidden, and IDOR probes.

---

## 2. Comprehensive Endpoint Test Matrix (All 14 API Groups)

| Group | Endpoint | Scenario Tested | Expected Status & Response | Actual Status & Response | Status |
|---|---|---|---|---|---|
| **1. Health & Readiness** | `GET /api/v1/health` | Liveness check (`X-Request-ID: req-12345678`) | `200 OK`, `{"status":"ok"}`, echoes `x-request-id` | `200 OK`, `{"status":"ok"}`, `x-request-id: req-12345678` | **PASS** |
| **1. Health & Readiness** | `GET /api/v1/ready` | DB reachable (`SELECT 1`) | `200 OK`, `{"status":"ready","database":"ok"}` | `200 OK`, `{"status":"ready","database":"ok"}` | **PASS** |
| **1. Health & Readiness** | `GET /api/v1/ready` | Simulated DB outage (`ping_database` raises `ConnectionError`) | `503 Service Unavailable`, `{"status":"unavailable","database":"unreachable"}` | `503 Service Unavailable`, `{"status":"unavailable","database":"unreachable"}` | **PASS** |
| **1. Health & Readiness** | `GET /docs` | Browser-accessible Swagger UI | `200 OK`, HTML with per-request CSP `script-src 'nonce-...'` | `200 OK`, nonce-CSP verified, zero `unsafe-inline` in `script-src` | **PASS** |
| **2. Authentication** | `POST /api/v1/auth/register` | Valid registration (`Manager.One@Hospital.Example`) | `201 Created`, normalized lowercase email, `role: "manager"`, `is_active: true` | `201 Created`, `{"email":"manager.one@hospital.example","role":"manager","is_active":true}` | **PASS** |
| **2. Authentication** | `POST /api/v1/auth/register` | Duplicate email submission | `409 Conflict`, `error.code == "conflict"` | `409 Conflict`, `error.code == "conflict"` | **PASS** |
| **2. Authentication** | `POST /api/v1/auth/register` | Missing required fields (`{}`) | `422 Unprocessable Content`, `error.code == "validation_error"` | `422 Unprocessable Content`, `error.code == "validation_error"` | **PASS** |
| **2. Authentication** | `POST /api/v1/auth/register` | Weak/breached password (`password1234`) | `422 Unprocessable Content`, `error.code == "weak_password"` | `422 Unprocessable Content`, `error.code == "weak_password"` | **PASS** |
| **2. Authentication** | `POST /api/v1/auth/login` | Valid credentials | `200 OK`, `access_token` (`expires_in: 900`) + `Set-Cookie: careops_refresh=...; HttpOnly; Path=/api/v1/auth; SameSite=strict; Secure` | `200 OK`, token + `HttpOnly; SameSite=strict; Secure` cookie issued | **PASS** |
| **2. Authentication** | `POST /api/v1/auth/login` | Wrong password / Unknown email | `401 Unauthorized` with identical generic message | `401 Unauthorized`, identical message for unknown user and wrong password | **PASS** |
| **2. Authentication** | `POST /api/v1/auth/login` | Exceed `10/minute` rate limit | `429 Too Many Requests` (`rate_limited`) | `429 Too Many Requests` on 11th request within 1 minute | **PASS** |
| **2. Authentication** | `POST /api/v1/auth/refresh` | Valid refresh cookie + allowed `Origin` | `200 OK`, rotates refresh cookie & issues new access token | `200 OK`, `second_refresh != first_refresh` | **PASS** |
| **2. Authentication** | `POST /api/v1/auth/refresh` | Disallowed `Origin: https://evil.example.com` | `403 Forbidden`, `error.code == "forbidden"` | `403 Forbidden`, `error.code == "forbidden"` | **PASS** |
| **2. Authentication** | `POST /api/v1/auth/logout` | Sign out active session | `204 No Content`, revokes token family & clears cookie | `204 No Content`, subsequent `/auth/refresh` returns `401` | **PASS** |
| **2. Authentication** | `GET /api/v1/auth/me` | Valid bearer token vs. unauthenticated | `200 OK` (`UserOut`) / `401 Unauthorized` without token | `200 OK` / `401 Unauthorized` | **PASS** |
| **3. Business Profile** | `GET /api/v1/business-profile` | Before profile creation | `404 Not Found` | `404 Not Found` | **PASS** |
| **3. Business Profile** | `PUT /api/v1/business-profile` | Create & update profile (`company_name`, `industry`, `team_size`, `business_goals`) | `200 OK`, persists in PostgreSQL, isolated per user | `200 OK`, persisted & isolated (`u2` still receives `404`) | **PASS** |
| **3. Business Profile** | `PUT /api/v1/business-profile` | Invalid data type (`team_size: "not-an-int"`) | `422 Unprocessable Content`, `error.code == "validation_error"` | `422 Unprocessable Content`, `error.code == "validation_error"` | **PASS** |
| **4. Dataset Management** | `POST /api/v1/datasets` | Manager uploads `01_Healthcare.xlsx` or 5 `.csv` files | `201 Created`, `7,100` rows loaded, `0` quarantined, `duplicate_batch_no` warning | `201 Created`, all 8 domain tables populated transactionally | **PASS** |
| **4. Dataset Management** | `POST /api/v1/datasets` | Analyst attempts dataset upload | `403 Forbidden` | `403 Forbidden` | **PASS** |
| **4. Dataset Management** | `POST /api/v1/datasets` | Malicious/invalid files (`.xlsm` macro, fake `.xlsx`, binary `.csv`, oversized) | `422`/`400` `UploadValidationError`, zero DB rows written | Rejected with structured error before DB load | **PASS** |
| **4. Dataset Management** | `GET /api/v1/datasets` | Paginated listing (Owner vs. Other Manager vs. Admin) | Owner sees own (`1`), Other Manager sees `0`, Admin sees all (`1`) | Verified exact isolation and pagination envelope | **PASS** |
| **4. Dataset Management** | `GET /api/v1/datasets/{id}` & `/quality-report` | Owner vs. Nonexistent UUID vs. Other Manager (IDOR) | Owner: `200 OK`; Nonexistent / Other Manager: `404 Not Found` | Owner: `200 OK`; Nonexistent / Other Manager: `404 Not Found` | **PASS** |
| **4. Dataset Management** | `DELETE /api/v1/datasets/{id}` | Owner deletes dataset vs. Other Manager IDOR | Owner: `204 No Content` + cascades domain rows; Other Manager: `404` | `204 No Content` for owner (`GET` then returns `404`); `404` for other manager | **PASS** |
| **5. Analytics** | `GET /api/v1/datasets/{id}/kpis` | Full range & filtered range (`?from=2026-05&to=2026-07`) | `200 OK`, 9 KPI cards matching golden values (`1,238` appts for May–Jul) | `200 OK`, exact golden values and filtered sums | **PASS** |
| **5. Analytics** | `GET /api/v1/datasets/{id}/kpis` | Invalid month format (`?from=bad`) or inverted range (`from=2026-09&to=2026-06`) | `400 Bad Request` | `400 Bad Request` | **PASS** |
| **5. Analytics** | `GET /api/v1/datasets/{id}/trends` | Monthly revenue/expenses, appointment status stacks, anomalies | `200 OK`, 6 monthly points (`[426, 399, 413, 442, 408, 412]`) | `200 OK`, exact 6-month series and anomaly list | **PASS** |
| **5. Analytics** | `GET /api/v1/datasets/{id}/breakdowns/{dimension}` | All 9 allowed dimensions + unknown dimension (`unknown`) + IDOR | `200 OK` for all 9 dimensions; `400` for `unknown`; `404` for non-owner | `200 OK` for all 9 dimensions; `400` for `unknown`; `404` for non-owner | **PASS** |
| **6 & 7. Analyses & Agent Monitor** | `POST /api/v1/analyses` | Manager enqueues analysis vs. Duplicate active run vs. Analyst | Manager: `202 Accepted` (6 queued agents); Duplicate: `409 Conflict`; Analyst: `403` | `202 Accepted`, `409 Conflict` on duplicate, `403 Forbidden` for analyst | **PASS** |
| **6 & 7. Analyses & Agent Monitor** | `GET /api/v1/analyses/{id}` & `/agents` | Poll run status, revision count, verdict, and per-agent logs (`context_from`, `tool_calls`, `output`) | `200 OK` for owner/admin; `404 Not Found` for other manager | `200 OK` with full agent logs; `404` for other manager | **PASS** |
| **6 & 7. Analyses & Agent Monitor** | `POST /api/v1/analyses/{id}/cancel` | Cancel queued/running analysis | `200 OK`, `status: "cancelled"` | `200 OK`, `status: "cancelled"` | **PASS** |
| **8 & 9. Reports & PDF Generation** | `GET /api/v1/reports` & `GET /api/v1/reports/{id}` | List and inspect full 8-section verified BI report | `200 OK` (`verdict: "approved"`, 8 sections, findings, verification appendix, 3 recommendations); `404` on IDOR | `200 OK` for owner/admin; `404` for other manager and nonexistent UUID | **PASS** |
| **8 & 9. Reports & PDF Generation** | `GET /api/v1/reports/{id}/pdf` | Download executive PDF report | `200 OK`, `Content-Type: application/pdf`, `%PDF-` header (`> 5 KB`); `404` on IDOR | `200 OK`, valid multi-page PDF streamed; `404` for other manager | **PASS** |
| **10 & 11. Recommendations & HITL Approvals** | `GET /api/v1/recommendations` & `/{id}` | List (`?status=pending_approval`) and inspect recommendation detail | `200 OK`, returns 3 pending recommendations from approved report | `200 OK`, 3 recommendations with `evidence_metric_keys` | **PASS** |
| **10 & 11. Recommendations & HITL Approvals** | `POST /api/v1/recommendations/{id}/decision` | Manager approves rec 1, Admin rejects rec 2, Analyst attempts (`403`), Other Manager attempts (`404`), Duplicate decision (`409`) | `200 OK` (`execution_mode: "recorded_decision_only"`), `403` analyst, `404` IDOR | Verified `200 OK` with persisted `approval_history`, `403` analyst, `404` IDOR | **PASS** |
| **12. AI Chat** | `POST /api/v1/chat/sessions` & `GET /api/v1/chat/sessions` | Create and list dataset-grounded chat sessions | `201 Created` / `200 OK` (isolated per user) | `201 Created` / `200 OK` (`other` manager sees `0`) | **PASS** |
| **12. AI Chat** | `POST /api/v1/chat/sessions/{id}/messages` | Grounded metric Q&A, 4 data-limit trap questions, 1 off-topic prompt-injection refusal, IDOR (`404`) | `201 Created` with `cited_metric_keys` or honest refusal; `404` for non-owner | All 7 turns verified (`14` persisted messages in `GET .../messages`); `404` on IDOR | **PASS** |
| **13 & 14. Admin & History** | `GET /api/v1/admin/users`, `/analyses`, `/reports` | Admin vs. Manager (`403`) vs. Analyst (`403`) vs. Anonymous (`401`) | `200 OK` for `admin`; `403` for `manager`/`analyst`; `401` for anonymous | `200 OK` for `admin`; `403` for `manager`/`analyst`; `401` for anonymous | **PASS** |
| **13 & 14. Admin & History** | `PATCH /api/v1/admin/users/{id}` | Admin changes user role / deactivates user / attempts self-demotion | `200 OK` on role/active change; `400` (`self_lockout`) on self-demotion | `200 OK` (deactivated user's JWT immediately returns `401`); `400` on self-lockout | **PASS** |

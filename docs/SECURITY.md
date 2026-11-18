# Security — CareOps Intelligence

## 1. Threat Model Summary

| Threat Category | Attack Vector | Mitigation Implemented & Tested |
|---|---|---|
| **Credential Stuffing & Brute Force** | Automated password guessing on `/auth/login`, weak user passwords | `argon2id` hashing (`argon2-cffi`), constant-time verification with pre-computed dummy hash on unknown emails, 12–128 char policy + offline breached-password list (`common_passwords.txt`), email-substring rejection, `slowapi` rate limit (`10/minute` on `/auth/*`) |
| **Token Theft & Session Hijacking** | XSS reading tokens from `localStorage`, stolen refresh cookie replay | 15-minute `HS256` access tokens stored **in memory only** on the client; rotating 256-bit refresh tokens stored as SHA-256 digests in `refresh_tokens` families and sent in `httpOnly`, `Secure`, `SameSite=Strict` cookies scoped to `/api/v1/auth`. Re-using a rotated refresh token revokes the entire token family |
| **Broken Access Control & IDOR** | `analyst` attempting upload/approval, `manager` probing another manager's dataset/report UUID | Server-side FastAPI dependencies (`CurrentUser`, `ManagerOrAdmin`, `AdminUser`) re-read role and `is_active` from PostgreSQL on every request. `ensure_owner_or_admin` returns `404 Not Found` (never `403`) on non-owners to prevent resource enumeration |
| **Malicious File Upload** | Macro-infected Excel (`.xlsm` / `vbaProject.bin`), zip bombs, formula injection, binary files disguised as `.csv` | Magic-byte signature verification (`PK\x03\x04`), zip archive inspection rejecting `vbaProject.bin` and uncompressed size > 50 MB, `openpyxl` opened strictly with `read_only=True, data_only=True` (zero formula evaluation), upload caps (`10 MB`, `100,000 rows`) |
| **PII & Secret Exposure** | Patient names or phone numbers sent to LLM, API responses, or logs; API keys committed to Git | Phone numbers masked at ingestion (`******` + last 4 digits); agents only access aggregate metrics tools; `structlog` processor automatically redacts sensitive keys (`password`, `secret`, `token`, `api_key`, `phone`, `patient_name`); `.env` ignored and `gitleaks` enforced in pre-commit and CI |
| **LLM Hallucination & Prompt Injection** | Dataset text hijacking agent prompts, LLM inventing numbers or marketing ROI | Tool outputs wrapped in `<tool_output>...</tool_output>` delimiters; `dataset_id` bound server-side (not an LLM argument); `MAX_LLM_CALLS_PER_ANALYSIS=40` cap; two-layer verification (deterministic `verifier.py` recomputing every cited `metric_key` and scanning narrative text for unbacked numbers + Verification Agent); LLM output rendered as text (never raw HTML) |
| **Uncontrolled Autonomous Action** | AI agents automatically changing budgets, orders, or staffing | Mandatory Human-in-the-Loop (HITL): recommendations from approved reports with `requires_approval=True` are created as `pending_approval`; only `manager`/`admin` can decide; decisions are recorded in `approval_history` (`execution_mode: recorded_decision_only`) |

---

## 2. Security Controls Tested in Automated Suite

- [x] `argon2id` roundtrip, dummy-hash constant-time verification, and password policy rejection (`tests/test_security.py`)
- [x] JWT `exp`, `iss`, `aud`, `sub`, `jti`, and `typ=access` enforcement (`tests/test_security.py`)
- [x] Refresh token rotation and token-family revocation on reuse detection (`tests/test_auth_api.py`)
- [x] Origin header check on cookie-authenticated endpoints and `429` rate limiting (`tests/test_auth_api.py`)
- [x] Full RBAC matrix (`admin`, `manager`, `analyst`, unauthenticated) and admin self-lockout prevention (`tests/test_rbac_and_profile.py`)
- [x] Cross-user IDOR returning `404` across datasets, quality reports, analytics, analyses, reports, PDFs, recommendations, and chat sessions (`tests/test_ingestion_and_metrics.py`, `tests/test_analytics_api.py`, `tests/test_crew_and_worker.py`, `tests/test_reports_and_hitl.py`, `tests/test_chat_and_admin.py`)
- [x] Security headers (`Content-Security-Policy` without `unsafe-inline` for scripts, per-request nonce on `/docs`, HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`) and `415` Content-Type guard (`tests/test_rbac_and_profile.py`)
- [x] Validation errors strip submitted secret values (`tests/test_rbac_and_profile.py`)
- [x] Structured JSON log redaction of secrets and PII (`tests/test_security.py`)
- [x] Macro `.xlsx`, fake zip, binary `.csv`, and oversized upload rejection (`tests/test_ingestion_and_metrics.py`)
- [x] Deterministic verifier catching mismatched metric values and unbacked numeric claims (`tests/test_crew_and_worker.py`)
- [x] HITL rule blocking `analyst` approvals (`403`) and blocking pending recommendations on rejected reports (`tests/test_crew_and_worker.py`, `tests/test_reports_and_hitl.py`)

---

## 3. Supply Chain & Container Hardening

- Dependencies are locked in `backend/uv.lock` and `frontend/package-lock.json` and audited in CI (`pip-audit`, `npm audit --omit=dev`).
- Backend Docker image (`backend/Dockerfile`) uses a multi-stage build on `python:3.12-slim` and runs as non-root user `app` (`uid 10001`).
- Frontend Docker image (`frontend/Dockerfile`) runs on `nginxinc/nginx-unprivileged` (`uid 101`).

## 4. Reporting a Vulnerability

Report security issues privately to the repository owner; do not open a public issue.

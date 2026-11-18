# Security

> Threat model summary and tested controls (updated each phase; finalized in Phase 7).

## Controls in place (through Phase 2)

- **Upload Hardening & PII Protection:**
  - Accepts only `.xlsx` (OOXML zip magic-byte check, rejects `vbaProject.bin` / `.xlsm` macros and zip-bombs > 50 MB uncompressed, opened in `openpyxl` `read_only=True, data_only=True` mode with zero formula evaluation) or the 5 entity `.csv` files (rejects binary magic bytes and null bytes).
  - Enforces upload size (`MAX_UPLOAD_MB=10`) and row (`MAX_UPLOAD_ROWS=100,000`) caps.
  - Phone numbers are masked at ingestion time (`******` + last 4 digits) before storage, and `patient_name` is never exposed by any API response or log.
  - Out-of-period dates, negative amounts, `net_amount != gross - discount`, duplicate PKs, and orphan FKs are quarantined with structured reasons in `datasets.quality_report`.

- **Passwords:** hashed with `argon2id` (`argon2-cffi`); constant-time verification including a
  pre-computed dummy hash on unknown emails so login timing never leaks account existence;
  policy requires 12-128 chars, rejects bundled common/breached passwords, repetitive or sequential
  strings, and passwords containing the user's email local-part.
- **JWT & Session Management:** 15-minute HS256 access tokens kept in memory only, with explicit
  validation of `exp`, `iat`, `nbf`, `iss`, `aud`, `sub`, `jti`, and `typ=access`. Refresh tokens
  are 256-bit random values stored server-side only as SHA-256 hashes in rotation families
  (`refresh_tokens` table) and sent in an `httpOnly`, `Secure`, `SameSite=Strict` cookie scoped to
  `/api/v1/auth`. Presenting an already-rotated refresh token immediately revokes the entire token
  family (reuse detection).
- **RBAC & Object-Level Authorization:** roles `admin`, `manager`, `analyst` are enforced in FastAPI
  dependencies (`app/api/deps.py`) and re-read from the database on every request so deactivation or
  demotion takes effect immediately. Non-owners receive `404 Not Found` (not `403`) via
  `ensure_owner_or_admin` to prevent IDOR enumeration.
- **Platform & Headers:** strict CORS allowlist (`CORS_ORIGINS`), Origin header verification on
  cookie-authenticated routes, rate limiting (`slowapi`, stricter `10/minute` on `/auth/*`),
  `Content-Security-Policy` without `unsafe-inline` for scripts (Swagger UI uses a per-request
  cryptographic nonce), `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, request size limits (413), Content-Type
  enforcement (415), and a single error envelope that never leaks stack traces or secret input
  values.
- **Structured Logging:** `structlog` JSON logs with `request_id` correlation and automatic
  redaction of sensitive keys (`password`, `secret`, `token`, `authorization`, `cookie`, `api_key`,
  `phone`, `patient_name`).
- **Supply Chain & Secrets:** `.env` ignored, gitleaks in pre-commit and CI, locked dependencies
  (`backend/uv.lock`, `frontend/package-lock.json`), non-root container (`uid 10001`).

## Planned (by phase)

- Phase 2: upload hardening (extension + magic-byte signature checks, no formula evaluation,
  size/row caps, transactional loading, phone masking).
- Phase 4-6: LLM prompt-injection rules, read-only dataset-scoped tools, aggregates-only context,
  call caps.

## Reporting a vulnerability

Contact the repository owner privately; do not open a public issue.

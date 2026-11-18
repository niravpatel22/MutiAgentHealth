# Security

> Stub (Phase 0). Threat model summary and the tested-controls list are completed in Phase 7.

## Controls in place (Phase 0)

- `.env` files are git-ignored; `.env.example` documents every variable with no real values.
- gitleaks runs as a pre-commit hook and in CI over the full Git history.
- Dependencies are locked (`backend/uv.lock`, `frontend/package-lock.json`) and audited in CI
  (`pip-audit`, `npm audit`); see `DECISIONS.md` D-016 for the dev-tooling exception.
- Backend container runs as a non-root user (uid 10001) on `python:3.12-slim` with no secrets baked in.
- CORS uses an explicit allowlist from `CORS_ORIGINS`.

## Planned (by phase)

- Phase 1: argon2id, JWT (15 min access in memory, rotating httpOnly refresh cookie with reuse
  detection), RBAC + object-level authorization, rate limiting, security headers, error envelope.
- Phase 2: upload hardening (signature checks, no formula evaluation, size/row caps).
- Phase 4–6: LLM prompt-injection rules, read-only dataset-scoped tools, aggregates-only context,
  call caps.

## Reporting a vulnerability

Contact the repository owner privately; do not open a public issue.

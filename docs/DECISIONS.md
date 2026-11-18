# Decisions log

Questions, ambiguities, and the defaults chosen. Each entry is reviewable by the client;
changing a default later is a config or small code change unless noted.

| ID | Topic | Decision (default) | Status |
|---|---|---|---|
| D-001 | Repo root | The workspace folder is the repo root (the brief's `healthcare-bi/` layout starts here). | Accepted |
| D-002 | LLM provider | Provider-agnostic via CrewAI's LiteLLM-backed `LLM(model=...)`. Example default `LLM_MODEL=gemini/gemini-2.5-flash`. Switching provider = env change only. LLM is mocked in all tests. | Accepted, provider confirmable |
| D-003 | CrewAI version | Pinned to the current stable release after checking official docs at the start of Phase 4 (not from memory). | Pending (Phase 4) |
| D-004 | Branding | Product name **CareOps Intelligence**, teal `#0E7C86` accent, no logo. | Default, confirmable |
| D-005 | Admin seed | First admin from `ADMIN_EMAIL` / `ADMIN_PASSWORD` env vars; no default values in code. | Accepted |
| D-006 | Report "as of" date | Dataset end date **2026-10-31** is the reference date for expiry windows and for treating Scheduled appointments as pipeline. | Accepted |
| D-007 | Margin basis | Default margin basis = **Approved** expenses. Pending shown as exposure; Rejected shown but never counted as cost. Basis is always stated. | Accepted |
| D-008 | Money handling | `Decimal` / `NUMERIC(14,2)` end to end. "Rounded ₹" golden values are compared after rounding to the nearest rupee. | Accepted |
| D-009 | Breached-password check | Offline: bundled list of common passwords + minimum length 12. No HIBP network call (would be an unlisted integration). | Accepted |
| D-010 | Upload storage | Uploaded files are processed in a temp directory and deleted afterwards; the database is the system of record. | Accepted |
| D-011 | Phone numbers | Stored in the domain table; every API response and log shows at most the last 4 digits. | Accepted |
| D-012 | Async work | Only analyses run in the DB-backed worker. Upload, chat, and PDF run synchronously (data volume is small). | Accepted |
| D-013 | Repo / hosting ownership | Private GitHub repo, GitHub Actions CI; owner pushes and deploys, URLs filled into `HANDOVER.md`. | Accepted |
| D-014 | Analysis limits | `MAX_LLM_CALLS_PER_ANALYSIS=40`, `ANALYSIS_TIMEOUT_SECONDS=900`, both env-configurable. | Accepted |
| D-015 | Revision loop | Each revision re-runs Strategy then Verification only (max 2), orchestrated by the service layer. | Accepted |
| D-016 | Dev-tooling npm advisory | `picomatch` (all versions, latest 4.0.7) has a high ReDoS advisory with no patched release; it is only a transitive dependency of Vite/Vitest at build/test time and never ships in the browser bundle. CI **blocks** on `npm audit --omit=dev` (production deps: 0 vulnerabilities) and **reports** the full audit as a warning. Revisit when a fix is published. | Accepted |
| D-017 | Python toolchain | Python 3.12 managed by `uv`; `backend/uv.lock` is the cross-platform lockfile used locally, in CI, and in the Docker image. | Accepted |
| D-018 | Frontend tooling versions | React stays on 18.3 (mandated). Vite 8 / Vitest 5 / jsdom (current majors). ESLint stays on 9 because `eslint-plugin-react` does not yet support ESLint 10. | Accepted |
| D-019 | Local environment | Dev machine is native Windows without Docker; Docker-based checks (`docker compose up`, image build) are verified in CI until Docker Desktop is installed locally. | Open: install Docker Desktop |

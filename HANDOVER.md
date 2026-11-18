# Client Handover Package — CareOps Intelligence

**Project:** AI-Powered Smart Business Operations & Decision Intelligence System (Healthcare Edition)
**Dataset:** `data/01_Healthcare.xlsx` (May 1 – Oct 31, 2026, INR)
**Version:** `v1.0.0`

---

## 1. Submission & Deployment Links

| Deliverable | Location / URL | Status |
|---|---|---|
| **GitHub Repository** | https://github.com/niravpatel22/MutiAgentHealth | Linked (`origin`) |
| **Live Frontend URL** | `<FILL_AFTER_VERCEL_OR_NETLIFY_DEPLOY>` | Config ready ([`frontend/vercel.json`](frontend/vercel.json)) |
| **Live Backend URL** | `<FILL_AFTER_RENDER_BLUEPRINT_DEPLOY>` | Blueprint ready ([`render.yaml`](render.yaml)) |
| **Live Swagger / OpenAPI URL** | `<LIVE_BACKEND_URL>/docs` | Nonce-CSP protected Swagger UI |
| **React.js Frontend Source** | [`/frontend`](frontend/) | Builds with 0 warnings, 7 Vitest tests passing |
| **FastAPI Backend Source** | [`/backend`](backend/) | 31 pytest tests passing, ~90% coverage |
| **CrewAI 6-Agent Implementation** | [`/backend/app/agents`](backend/app/agents/) | Sequential task context chaining + 2-layer verifier |
| **Database Schema & Migrations** | [`/backend/alembic/versions`](backend/alembic/versions/) | `0001_initial_app` + `0002_domain_healthcare` |
| **Architecture Diagram** | [`docs/architecture.png`](docs/architecture.png) & [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Committed |
| **Sample Generated PDF Report** | [`docs/sample_report.pdf`](docs/sample_report.pdf) | Committed (`44,772` bytes, from approved run) |
| **Demonstration Video (6–8 min)** | `<FILL_VIDEO_URL_AFTER_RECORDING>` | Script ready at [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) |

---

## 2. Demo Role Credentials (Local / Seeded Defaults)

> Passwords are never hardcoded in application code. The table below lists the local development
> accounts seeded via `backend/.env` and the registration flow. In production, set `ADMIN_EMAIL`
> and `ADMIN_PASSWORD` in your host's environment settings.

| Role | Email | Password (Local Dev) | Capabilities |
|---|---|---|---|
| **Admin** | `admin@careops.local` |Set via `ADMIN_PASSWORD` in `.env` | Full access: user/role management, all datasets, analyses, reports, and HITL approvals |
| **Manager** | Register via `/register` (e.g. `manager@hospital.example`) | 12+ chars chosen at registration | Upload datasets, view dashboard, run 6-agent analyses, approve/reject HITL recommendations, download PDF, use AI chat |
| **Analyst** | Created/assigned by Admin via `/admin` | 12+ chars | Read-only access to dashboards, reports, and AI chat; **cannot** upload datasets or approve/reject recommendations (`403 Forbidden`) |

---

## 3. First-Day Operations Guide

### Starting & Verifying the System
1. **Health & Readiness:**
   - Liveness: `GET /api/v1/health` → `{"status": "ok"}`
   - Database readiness: `GET /api/v1/ready` → `{"status": "ready", "database": "ok"}`
2. **Seeding the Admin & Sample Dataset:**
   ```bash
   cd backend
   uv run alembic upgrade head
   uv run python -m app.cli seed-admin
   uv run python -m app.cli load-sample-dataset
   ```
3. **Switching LLM Providers:**
   - Update `LLM_MODEL` and `LLM_API_KEY` in the backend environment settings (for example `gemini/gemini-2.5-flash`, `openai/gpt-4o-mini`, or `anthropic/claude-3-5-sonnet-latest`) and restart the `api` and `worker` services. No code changes are required.
4. **Rotating Secrets:**
   - Rotate `JWT_SECRET` in the host environment to immediately invalidate all active access tokens.
   - Deactivating a user in the **Admin Console** (`/admin`) immediately revokes all of their active refresh token families and blocks their access tokens on the next request.

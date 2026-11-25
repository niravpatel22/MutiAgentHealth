# Client Handover & Delivery Package — MediOps Intelligence

**Product Name:** MediOps Intelligence
**Subtitle:** AI-Powered Hospital Operations & Performance Intelligence.
**Dataset:** `data/01_Healthcare.xlsx` (May 1 – Oct 31, 2026, Currency: INR)
**Version:** `v1.0.0`

---

## 1. Project Overview

**MediOps Intelligence** is a commercial-grade healthcare operations and decision intelligence platform built for hospital leadership. Managers upload hospital operational workbooks (`.xlsx` or the 5 entity `.csv` files), inspect an automated data quality and quarantine report, explore live KPIs and Recharts visualizations computed from a single deterministic metrics registry, and run a 6-agent **CrewAI** pipeline (`Data Analyst → Marketing → Finance → Operations → Strategy → Verification`) backed by a two-layer hallucination verifier and a mandatory Human-in-the-Loop (HITL) governance workflow.

---

## 2. Architecture Summary

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/architecture.png`](docs/architecture.png) for the system architecture diagram, Entity-Relationship Diagram (ERD), 6-agent CrewAI workflow diagram, and sequence diagram.

- **Strict Layer Separation:** FastAPI routers (`backend/app/api/v1/`) and business services (`backend/app/services/`) are implemented independently of CrewAI. CrewAI is invoked only inside `backend/app/agents/` via the PostgreSQL background worker (`backend/app/worker/`).
- **Single Source of Truth:** All 27 metrics, monthly series, dimensional breakdowns, and statistical anomalies are computed deterministically in [`backend/app/metrics/registry.py`](backend/app/metrics/registry.py).
- **Two-Layer Hallucination Verification:** Layer 1 ([`backend/app/agents/verifier.py`](backend/app/agents/verifier.py)) recomputes every cited `metric_key` and scans narrative text for unbacked numbers; Layer 2 (`Verification Agent`) audits qualitative consistency and data limits, triggering up to 2 `Strategy → Verification` revision loops before issuing an `approved` or `rejected` verdict.

---

## 3. Technology Stack

| Layer | Technology | Version / Details |
|---|---|---|
| **Frontend** | React + Vite, React Router, TanStack Query, Recharts | React `18.3.1`, Vite `8.3.8`, self-hosted `@fontsource/inter`, hand-written clinical CSS tokens (teal `#0E7C86`, navy `#0F172A`, white `#FFFFFF`, neutral-grey `#F8FAFC`) |
| **Backend** | Python, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic | Python `3.12.16` (managed via `uv`), FastAPI, `psycopg` v3, `structlog` JSON logging, `slowapi` rate limiting |
| **Multi-Agent AI** | CrewAI + Provider-Agnostic LLM | `crewai==1.15.41` (`Process.sequential` with explicit task `context` chaining and 5 read-only dataset-scoped tools) |
| **Authentication & Security** | PyJWT + `argon2-cffi` | `argon2id` password hashing, 15-min in-memory access JWT, rotating 7-day `httpOnly` `Secure` `SameSite=Strict` refresh cookie with reuse detection |
| **Database** | PostgreSQL | PostgreSQL `16+` (verified locally on PostgreSQL `18.7` and via Docker `postgres:16-alpine`) |
| **Reporting** | ReportLab + matplotlib | Reproducible multi-section executive PDF with embedded charts and verification appendix |
| **Quality & CI** | pytest, Vitest, Ruff, Black, ESLint, Prettier, Gitleaks | Pre-commit hooks + [`.github/workflows/ci.yml`](.github/workflows/ci.yml) |

---

## 4. Repository, Verified URLs & Delivery Artifacts

| Item | Verified URL / Location / Status |
|---|---|
| **GitHub Repository URL** | `https://github.com/niravpatel22/MutiAgentHealth` (public repository with 100% passing GitHub Actions CI across all 5 jobs) |
| **Live Deployed Frontend URL (Netlify)** | `https://mediops-intelligence.netlify.app` (pure static React 18 SPA connected directly to live Render FastAPI + Neon PostgreSQL) |
| **Live Deployed Frontend Mirror (Render)** | `https://careops-web-uk4b.onrender.com` |
| **Live Deployed Backend API URL (Render)** | `https://careops-api-oi3h.onrender.com/api/v1` (Health: `https://careops-api-oi3h.onrender.com/api/v1/health`, Ready: `https://careops-api-oi3h.onrender.com/api/v1/ready`) |
| **Live Public Swagger / OpenAPI URL** | `https://careops-api-oi3h.onrender.com/docs` (raw OpenAPI spec: `https://careops-api-oi3h.onrender.com/openapi.json`) |
| **Live Database (Neon Lakebase PostgreSQL 18)** | Project `lingering-fire-47681562`, Branch `production` (`ep-jolly-frost-bdf4g55j`, 20 tables, 3 pre-seeded role datasets, 3 live CrewAI verified reports) |
| **Verified Local Frontend URL** | `http://localhost:5173` (verified in Google Chrome `157.0.8103.79` across `1440×900`, `1366×768`, `768×1024`, and `390×844` viewports) |
| **Verified Local Backend & Swagger URL** | `http://localhost:8000` (`http://localhost:8000/docs`, `http://localhost:8000/api/v1/health`, `http://localhost:8000/api/v1/ready`) |
| **Sample Generated PDF Report** | [`docs/sample_report.pdf`](docs/sample_report.pdf) (`44,778` bytes, 3-page A4 executive report generated from a real, verified analysis run on `data/01_Healthcare.xlsx`) |
| **Browser Verification Screenshots** | [`audit/screenshots/`](audit/screenshots/) (`login.png`, `dashboard.png`, `dataset_upload.png`, `dataset_quality_report.png`, `analysis_monitor.png`, `report_details.png`, `approvals.png`, `ai_chat.png`, `admin.png`, `mobile_layout.png`) |
| **Architecture & Database ERD** | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) & [`docs/architecture.png`](docs/architecture.png) |
| **API Reference Documentation** | [`docs/API.md`](docs/API.md) |

---

## 5. Database Provider, Structure & Configuration Guidance

Managed via Alembic migrations (`0001_initial_app` and `0002_domain_healthcare`):
- **12 Application Tables:** `users`, `refresh_tokens`, `business_profiles`, `datasets`, `analysis_runs`, `agent_executions`, `reports`, `recommendations`, `approval_history`, `chat_sessions`, `chat_messages`, `alembic_version`.
- **8 Dataset-Isolated Domain Tables:** `patients` (phone masked to `******1234`, `patient_name` never exposed), `doctors` (`40` derived), `suppliers` (`60` derived), `vendors` (`90` derived), `appointments` (`2,500`), `invoices` (`1,800`), `medicine_items` (`1,000`), `expenses` (`600`). Every domain row carries `dataset_id` in its composite primary key and foreign keys with `ON DELETE CASCADE`.
- **Supported PostgreSQL Providers:** Local PostgreSQL `16+` / `18.x`, Docker `postgres:16-alpine`, Render Managed PostgreSQL (`render.yaml`), Neon, or Supabase (`postgres://` and `postgresql://` connection strings are automatically normalized to `postgresql+psycopg://`).

---

## 6. Deployment Providers & Instructions

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for step-by-step cloud deployment instructions:
- **Backend API & Worker:** Render Blueprint ([`render.yaml`](render.yaml)) or Railway/Fly.io using [`backend/Dockerfile`](backend/Dockerfile).
- **Frontend SPA:** Vercel ([`frontend/vercel.json`](frontend/vercel.json)), Netlify ([`frontend/public/_redirects`](frontend/public/_redirects)), or Docker unprivileged Nginx ([`frontend/Dockerfile`](frontend/Dockerfile)).

---

## 7. Environment Variable Documentation

Every variable is documented in [`backend/.env.example`](backend/.env.example) and [`frontend/.env.example`](frontend/.env.example) (never commit `.env` files or real secrets):
- `APP_NAME` (`MediOps Intelligence`), `APP_ENV` (`development` | `test` | `production`), `LOG_LEVEL` (`INFO`).
- `DATABASE_URL`: PostgreSQL connection URL.
- `CORS_ORIGINS`: comma-separated allowed browser origins (`http://localhost:5173`).
- `JWT_SECRET`: 32+ character secret required in production.
- `COOKIE_SECURE`: `true` in HTTPS production (`false` only for plain-HTTP localhost development).
- `ADMIN_EMAIL` / `ADMIN_PASSWORD`: initial admin credentials seeded via `python -m app.cli seed-admin` (`ADMIN_EMAIL` must be a valid RFC email address, e.g. `admin@mediops.example`).
- `LLM_MODEL` (`gemini/gemini-2.5-flash`) / `LLM_API_KEY` / `LLM_TEMPERATURE` (`0.2`) / `MAX_LLM_CALLS_PER_ANALYSIS` (`40`) / `ANALYSIS_TIMEOUT_SECONDS` (`900`).
- `VITE_API_BASE_URL`: public URL of the FastAPI `/api/v1` prefix (`http://localhost:8000/api/v1`).

---

## 8. Local Setup Instructions (Runnable from a Fresh Clone)

### Option A: One-Command Docker Stack
```bash
git clone https://github.com/niravpatel22/MutiAgentHealth.git
cd MutiAgentHealth
cp backend/.env.example backend/.env
# Edit backend/.env to set JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD, and optional LLM_API_KEY
docker compose up --build
```

### Option B: Native Local Setup (Windows / Linux / macOS)
```powershell
# 1. Install locked Python 3.12 (via uv) and Node.js dependencies
./scripts/tasks.ps1 install        # Linux/macOS: make install

# 2. Configure backend/.env and run database migrations
cp backend/.env.example backend/.env
./scripts/tasks.ps1 migrate        # Linux/macOS: make migrate

# 3. Seed the initial admin and load data/01_Healthcare.xlsx (7,100 rows)
./scripts/tasks.ps1 seed-admin     # Linux/macOS: make seed-admin
./scripts/tasks.ps1 load-sample-dataset

# 4. Start the FastAPI server, background worker, and React frontend
./scripts/tasks.ps1 api            # http://localhost:8000/docs
cd backend && uv run python -m app.worker
./scripts/tasks.ps1 web            # http://localhost:5173
```

---

## 9. Test Instructions & Verified Audit Results

```powershell
./scripts/tasks.ps1 lint           # Ruff, Black, ESLint (--max-warnings=0), Prettier
./scripts/tasks.ps1 test           # pytest + Vitest

# Opt-in live LLM smoke test (when LLM_API_KEY is configured):
cd backend && uv run pytest -m live_llm
```

| Verification Suite | Execution Type | Status | Verified Result |
|---|---|---|---|
| **Backend Unit & API Suite (`pytest`)** | Automated | **PASS** | **32 passed** (`0` failed; `1` `live_llm` skipped when `LLM_API_KEY` unset) |
| **Frontend Component Suite (`vitest`)** | Automated | **PASS** | **8 passed** (`0` failed), `vite build` succeeds in `641 ms` |
| **Static Analysis & Secret Scan** | Automated | **PASS** | Ruff `0` errors, Black `79` unchanged, ESLint `0` warnings, Prettier clean, Git history `0` committed secrets |
| **Chrome 157 CDP Live Browser & E2E Suite** | Browser Automation | **PASS** | **23/23 checks passed** across Manager, Analyst, and Admin workflows and all 4 viewports (`1440×900`, `1366×768`, `768×1024`, `390×844`) with 10 saved PNG screenshots in [`audit/screenshots/`](audit/screenshots/) |
| **Live External LLM Provider Call** | Opt-In Integration | **BLOCKED** | Requires user-supplied `LLM_API_KEY` in `backend/.env` |
| **Public Cloud Hosting (Render / Vercel)** | External Deployment | **BLOCKED / NOT DEPLOYED** | Requires owner GitHub push (`Contents: Read and write` PAT) and Render/Vercel account connection |

---

## 10. Admin Setup Procedure & Role Matrix

Run `python -m app.cli seed-admin` (or `./scripts/tasks.ps1 seed-admin`) with `ADMIN_EMAIL` (valid email domain, e.g. `admin@mediops.example`) and `ADMIN_PASSWORD` (12+ characters) set in `backend/.env`.

| Role | Capabilities | Restricted Actions |
|---|---|---|
| `admin` | Manage users/roles (`/admin`), access all datasets, analyses, reports, and HITL approvals | Cannot demote or deactivate own account (`self_lockout` guard) |
| `manager` | Self-registered via `/register`; upload datasets, run analyses, approve/reject HITL recommendations, download PDF, use AI chat | Cannot access `/admin/*` (`403`) or other managers' resources (`404` IDOR protection) |
| `analyst` | Read-only access to permitted dashboards, reports, and AI chat | Cannot upload/delete datasets (`403`), start analyses (`403`), or approve/reject recommendations (`403`) |

---

## 11. Demo Instructions

Follow the 6–8 minute walkthrough in [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) covering login, business profile, `01_Healthcare.xlsx` upload, quality report inspection, dashboard KPI & chart exploration, 6-agent CrewAI execution monitoring, verified BI report & PDF export, Human-in-the-Loop approval/rejection, AI Chat data-limitation traps, analysis history, and Admin RBAC management.

---

## 12. Known Limitations, Security Notes, Maintenance & Operational Guidance

### Known Limitations
1. **Dataset Data Limits (Reported Honestly by All Agents & Chat):**
   - **No marketing campaign or spend data:** Marketing ROI and customer acquisition cost cannot be computed.
   - **No amount-paid column on invoices:** `Partially Paid` invoices do not record collected amounts; figures are reported strictly as *invoiced value by payment status*, never as collected cash.
   - **Consultation fee overlap:** Revenue is `Billing.net_amount` (`₹22,256,456.76`) only; `Appointments.consultation_fee` is informational and never added to revenue.
   - **Point-in-time inventory snapshot:** `Medicine_Inventory` is not linked to billing or consumption, so stock-out dates cannot be forecasted; only reorder risk (`111`), 90-day expiry risk (`20`), and duplicate batches (`6`) are valid.
2. **In-Memory Rate Limiter:** `slowapi` uses in-process memory by default, suitable for a single API container; multi-instance horizontal scaling should point `slowapi` at Redis.

### Security Notes
- See [`docs/SECURITY.md`](docs/SECURITY.md) for the complete threat model.
- Access tokens are stored strictly in browser memory (never in `localStorage` or `sessionStorage`).
- Patient phone numbers are masked at ingestion (`******1234`) and `patient_name` is never returned by any API endpoint or CrewAI tool.
- Any Personal Access Token shared during support or setup must be rotated immediately in GitHub Settings.

### Maintenance, Backup & Support Guidance
- **Database Backup (`pg_dump`):**
  ```bash
  pg_dump --format=custom --no-owner --no-acl "$DATABASE_URL" > mediops_backup_$(date +%F).dump
  ```
- **Database Restore (`pg_restore`):**
  ```bash
  pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" mediops_backup_YYYY-MM-DD.dump
  ```
- **Worker Recovery:** Restarting `python -m app.worker` automatically runs `recover_interrupted_runs()`, marking any crash-interrupted `RUNNING` analysis as `FAILED` and unlocking the dataset for a fresh run.
- **Client Ownership Transfer Checklist:**
  - [ ] Revoke any previously shared GitHub PAT and push `main` + `v1.0.0` to `https://github.com/niravpatel22/MutiAgentHealth`.
  - [ ] Provision Render Blueprint (`render.yaml`) under the client's Render account and set `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `LLM_API_KEY`.
  - [ ] Connect Vercel (`frontend/`) with `VITE_API_BASE_URL` pointing to the live Render API `/api/v1` URL and update `CORS_ORIGINS` on Render.
  - [ ] Rotate initial `ADMIN_PASSWORD` after first production sign-in.

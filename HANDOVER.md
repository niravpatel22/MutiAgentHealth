# Client Handover & Delivery Package — MediOps Intelligence

**Product Name:** MediOps Intelligence
**Subtitle:** AI-Powered Hospital Operations & Performance Intelligence.
**Dataset:** `data/01_Healthcare.xlsx` (May 1 – Oct 31, 2026, INR)
**Version:** `v1.0.0`

---

## 1. Product Overview

**MediOps Intelligence** is a commercial-grade healthcare operations and decision intelligence platform built for hospital leadership. Managers upload hospital operational workbooks (`.xlsx` or the 5 entity `.csv` files), inspect an automated data quality and quarantine report, explore live KPIs and Recharts visualizations computed from a single deterministic metrics registry, and run a 6-agent **CrewAI** pipeline (`Data Analyst → Marketing → Finance → Operations → Strategy → Verification`) backed by a two-layer hallucination verifier and a mandatory Human-in-the-Loop (HITL) governance workflow.

---

## 2. Technology Stack

| Layer | Technology | Version / Details |
|---|---|---|
| **Frontend** | React + Vite, React Router, TanStack Query, Recharts | React `18.3.1`, Vite `8.3.8`, self-hosted `@fontsource/inter`, hand-written CSS tokens (teal `#0E7C86`, navy `#0F172A`, white `#FFFFFF`, neutral-grey `#F8FAFC`) |
| **Backend** | Python, FastAPI, Pydantic v2, SQLAlchemy 2.0, Alembic | Python `3.12.16`, FastAPI, `psycopg` v3, `structlog` JSON logging, `slowapi` rate limiting |
| **Multi-Agent AI** | CrewAI + Provider-Agnostic LLM | `crewai==1.15.41` (`Process.sequential` with explicit task `context` chaining and 5 read-only dataset-scoped tools) |
| **Authentication & Security** | PyJWT + `argon2-cffi` | `argon2id` password hashing, 15-min in-memory access JWT, rotating 7-day `httpOnly` `Secure` `SameSite=Strict` refresh cookie with reuse detection |
| **Database** | PostgreSQL | PostgreSQL `16+` (verified locally on PostgreSQL `18.7` and via Docker `postgres:16-alpine`) |
| **Reporting** | ReportLab + matplotlib | Reproducible multi-section executive PDF with embedded charts and verification appendix |
| **Quality & CI** | pytest, Vitest, Ruff, Black, ESLint, Prettier, Gitleaks | Pre-commit hooks + `.github/workflows/ci.yml` |

---

## 3. Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) and [`docs/architecture.png`](docs/architecture.png) for the full system architecture diagram, ERD, 6-agent workflow diagram, and sequence diagram.

- **Strict Layer Separation:** FastAPI routers (`backend/app/api/v1/`) and business services (`backend/app/services/`) are implemented independently of CrewAI. CrewAI is invoked only inside `backend/app/agents/` via the background worker (`backend/app/worker/`).
- **Single Source of Truth:** All 27 metrics, monthly series, dimensional breakdowns, and statistical anomalies are computed in [`backend/app/metrics/registry.py`](backend/app/metrics/registry.py).
- **Two-Layer Hallucination Verification:** Layer 1 ([`backend/app/agents/verifier.py`](backend/app/agents/verifier.py)) recomputes every cited `metric_key` and scans narrative text for unbacked numbers; Layer 2 (`Verification Agent`) audits qualitative consistency and data limits, triggering up to 2 `Strategy → Verification` revision loops before issuing an `approved` or `rejected` verdict.

---

## 4. Database Structure

Managed via Alembic migrations (`0001_initial_app` and `0002_domain_healthcare`):

- **12 Application Tables:** `users`, `refresh_tokens`, `business_profiles`, `datasets`, `analysis_runs`, `agent_executions`, `reports`, `recommendations`, `approval_history`, `chat_sessions`, `chat_messages`, `alembic_version`.
- **8 Dataset-Isolated Domain Tables:** `patients` (phone masked to `******1234`, `patient_name` never exposed), `doctors` (40 derived), `suppliers` (60 derived), `vendors` (90 derived), `appointments` (2,500), `invoices` (1,800), `medicine_items` (1,000), `expenses` (600). Every domain row carries `dataset_id` in its composite primary key and foreign keys with `ON DELETE CASCADE`.

---

## 5. Installation Instructions (Runnable from a Fresh Clone)

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

## 6. Environment Configuration

Every variable is documented in [`backend/.env.example`](backend/.env.example) and [`frontend/.env.example`](frontend/.env.example):
- `DATABASE_URL`: PostgreSQL connection string (`postgres://`, `postgresql://`, and `postgresql+psycopg://` are all accepted and auto-normalized).
- `JWT_SECRET`: 32+ character secret required in production.
- `CORS_ORIGINS`: comma-separated allowed browser origins (`http://localhost:5173`).
- `ADMIN_EMAIL` / `ADMIN_PASSWORD`: initial admin account seeded via `seed-admin`.
- `LLM_MODEL` / `LLM_API_KEY` / `LLM_TEMPERATURE` / `MAX_LLM_CALLS_PER_ANALYSIS` (`40`).
- `VITE_API_BASE_URL`: public URL of the FastAPI `/api/v1` prefix (`http://localhost:8000/api/v1`).

---

## 7. Admin Setup & Role Matrix

Run `python -m app.cli seed-admin` (or `./scripts/tasks.ps1 seed-admin`) with `ADMIN_EMAIL` and `ADMIN_PASSWORD` set in `backend/.env`.

| Role | Capabilities | Restricted Actions |
|---|---|---|
| `admin` | Manage users/roles (`/admin`), access all datasets, analyses, reports, and HITL approvals | Cannot demote or deactivate own account (`self_lockout` guard) |
| `manager` | Self-registered via `/register`; upload datasets, run analyses, approve/reject HITL recommendations, download PDF, use AI chat | Cannot access `/admin/*` (`403`) or other managers' resources (`404` IDOR protection) |
| `analyst` | Read-only access to dashboards, reports, and AI chat | Cannot upload/delete datasets (`403`), start analyses (`403`), or approve/reject recommendations (`403`) |

---

## 8. API Documentation & Verified Endpoints

- **Local Verified Backend URL:** `http://localhost:8000`
- **Local Verified Swagger / OpenAPI URL:** `http://localhost:8000/docs` (raw spec: `http://localhost:8000/openapi.json`)
- **Local Verified Frontend URL:** `http://localhost:5173`
- **Summary Reference:** [`docs/API.md`](docs/API.md)

---

## 9. Repository, Deployment URLs, & Artifacts

| Item | Value / Status |
|---|---|
| **GitHub Repository** | `https://github.com/niravpatel22/MutiAgentHealth` (remote `origin` configured; push requires repo owner's GitHub credentials) |
| **Verified Local Frontend URL** | `http://localhost:5173` (verified end-to-end across desktop `1440×900`, tablet `768×1024`, and mobile `390×844` viewports) |
| **Verified Local Backend URL** | `http://localhost:8000` (`/api/v1/health` and `/api/v1/ready` verified against live PostgreSQL `18.7`) |
| **Verified Local Swagger URL** | `http://localhost:8000/docs` |
| **Cloud Frontend / Backend URLs** | Pending owner push to GitHub and Render Blueprint / Vercel connection (see [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md); per Section 5, unverified cloud URLs are not fabricated) |
| **Sample Generated PDF Report** | [`docs/sample_report.pdf`](docs/sample_report.pdf) (generated from a real, verified analysis run on `data/01_Healthcare.xlsx`) |

---

## 10. Testing Results & Verification Matrix

| Verification Area | Status | Evidence |
|---|---|---|
| **Backend Automated Tests (`pytest`)** | **Completed & Verified** | **32 passed** (~90% coverage across `security.py`, `ingestion/`, `metrics/`, `verifier.py`, `tools.py`, `runner.py`, and API routers) |
| **Frontend Automated Tests (`vitest`)** | **Completed & Verified** | **7 passed**, `eslint --max-warnings=0` clean, `vite build` production bundle clean |
| **End-to-End Integration Workflow** | **Completed & Verified** | Verified live across PostgreSQL `18.7` + FastAPI + Worker + React UI: `Registration → Login → Business Profile → Dataset Upload → Validation → Import → Dashboard → Analysis Request → Worker → 6 Agents → Verification → Report → Manager Approval (+ Analyst 403) → PDF Download → Chat → History → Admin` |
| **Desktop, Tablet, & Mobile UI Verification** | **Completed & Verified** | Live browser inspection across `1440×900` (desktop), `768×1024` (tablet), and `390×844` (mobile) |
| **Worker Restart Recovery & Idempotency** | **Completed & Verified** | `recover_interrupted_runs` marks interrupted runs `failed` (never `completed`); duplicate report prevention verified in `test_worker_restart_recovery_and_idempotent_no_duplicate_reports` |
| **Live LLM Provider Execution** | **Opt-In / Configurable** |Deterministic tool-driven CrewAI execution runs when `LLM_API_KEY` is unset; setting `LLM_API_KEY` enables live provider calls (`pytest -m live_llm`) |
| **External Cloud Hosting (Render / Vercel)** | **Config Ready, Awaiting Owner Credentials** | `render.yaml`, `backend/Dockerfile`, `frontend/Dockerfile`, and `frontend/vercel.json` are committed; pushing to GitHub and activating Render/Vercel requires the repository owner's account login |

---

## 11. Known Limitations (Dataset & Architecture)

1. **Dataset Data Limits (Reported Honestly by All Agents & Chat):**
   - **No marketing campaign or spend data:** Marketing ROI and customer acquisition cost cannot be computed.
   - **No amount-paid column on invoices:** `Partially Paid` invoices do not record collected amounts; figures are reported strictly as *invoiced value by payment status*, never as collected cash.
   - **Consultation fee overlap:** Revenue is `Billing.net_amount` (`₹22,256,456.76`) only; `Appointments.consultation_fee` is informational and never added to revenue.
   - **Point-in-time inventory snapshot:** `Medicine_Inventory` is not linked to billing or consumption, so stock-out dates cannot be forecasted; only reorder risk (`111`), 90-day expiry risk (`20`), and duplicate batches (`6`) are valid.
2. **In-Memory Rate Limiter:** `slowapi` uses in-process memory by default, suitable for a single API container; multi-instance horizontal scaling should point `slowapi` at Redis.
3. **Synthetic / De-Identified Data Scope:** Designed for synthetic or de-identified operational data; loading real patient PII requires India DPDP Act compliance review.

---

## 12. Deployment, Backup, & Restore Instructions

- **Deployment:** Follow [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for Render (`render.yaml`) and Vercel (`frontend/vercel.json`).
- **Database Backup (`pg_dump`):**
  ```bash
  pg_dump --format=custom --no-owner --no-acl "$DATABASE_URL" > mediops_backup_$(date +%F).dump
  ```
- **Database Restore (`pg_restore`):**
  ```bash
  pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" mediops_backup_YYYY-MM-DD.dump
  ```

---

## 13. Client Ownership & Account Transfer Checklist

- [ ] **GitHub Repository:** Transfer `niravpatel22/MutiAgentHealth` to the client's GitHub Organization (or grant Admin access) and verify branch protection on `main`.
- [ ] **Render / Backend Hosting:** Provision the Render Blueprint under the client's billing account and set `JWT_SECRET`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and `LLM_API_KEY` in the Render environment settings.
- [ ] **Frontend Hosting (Vercel / Netlify):** Connect the client's Vercel/Netlify team to the GitHub repository with `VITE_API_BASE_URL` pointing to the client's live backend `/api/v1` URL.
- [ ] **LLM Provider Key:** Replace any developer `LLM_API_KEY` with a client-owned API key carrying a monthly spend cap in Google AI Studio / OpenAI / Anthropic Console.
- [ ] **Initial Admin Password Rotation:** Sign in with the seeded admin account, verify access to `/admin`, and rotate `ADMIN_PASSWORD` and `JWT_SECRET`.

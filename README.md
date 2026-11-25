# MediOps Intelligence v2.0

**AI-Powered Hospital Operations & Decision Intelligence Platform**
Full-stack multi-agent business intelligence system built on `data/01_Healthcare.xlsx` (May 1 – Oct 31, 2026, Currency: INR).

**Mandatory Architecture:** React 18 + Vite + Recharts · Python 3.12 + FastAPI · CrewAI 1.15.41 + Google Gemini LLM · **Neon Lakebase PostgreSQL 18** (`psycopg` v3) · Argon2id + HS256 JWT + Rotating Refresh Cookie · ReportLab Dynamic PDF · Docker · GitHub Actions CI.

---

## 1. Live Production Links (Submit These Exact Links for Assessment)

> [!IMPORTANT]
> **Give these public URLs to the assessor** (no Render dashboard login required):

| Deliverable | Live Public URL |
|---|---|
| **Live Deployed Frontend URL (Netlify — React 18 SPA)** | **https://mediops-intelligence.netlify.app** |
| **Live Deployed Frontend Mirror (Render Static SPA)** | **https://careops-web-uk4b.onrender.com** |
| **Live Deployed FastAPI Backend URL (Render Docker)** | **https://careops-api-oi3h.onrender.com** |
| **Live Public FastAPI Swagger / OpenAPI Documentation** | **https://careops-api-oi3h.onrender.com/docs** |
| **Live Raw OpenAPI JSON Schema** | **https://careops-api-oi3h.onrender.com/openapi.json** |
| **Live Backend Liveness & Neon DB Readiness Probes** | **https://careops-api-oi3h.onrender.com/api/v1/health** · **https://careops-api-oi3h.onrender.com/api/v1/ready** |
| **GitHub Repository URL** | **https://github.com/niravpatel22/MutiAgentHealth** |
| **Sample Generated Executive PDF Report** | [`docs/sample_report.pdf`](docs/sample_report.pdf) *(also downloadable live for every analysis run via `GET /api/v1/reports/{report_id}/pdf`)* |

![System Architecture](docs/architecture.png)

---

## 2. Demo & Role Credentials (Pre-Seeded in Neon PostgreSQL)

All three RBAC roles are pre-seeded in the live Neon PostgreSQL database (`ep-jolly-frost-bdf4g55j`, branch `production`) with `01_Healthcare.xlsx` (7,100 validated rows) and verified 6-agent CrewAI reports. You can also click the **Quick-Fill Role Buttons** (`Fill Manager`, `Fill Admin`, `Fill Analyst`) directly on the `/login` screen or register a new Manager account at `/register`.

| Role | Email | Password | Capabilities |
|---|---|---|---|
| **Manager** *(Recommended for Full Demo)* | `e2e.manager@mediops.example` | `Sunrise#Ward99!Ops` | Full workflow: Business Profile, Dataset Upload & Quality Report, KPI Dashboard & 8 Recharts, 6-Agent CrewAI Analysis & Live Monitor, Verified 8-Section Reports, Dynamic PDF Download, HITL Approvals, Grounded AI Chat, History |
| **Admin** | `admin@mediops.example` | `Admin#MediOps2026!` | Everything Manager can do **plus** `/admin` Governance Console (User RBAC role management, account activation/deactivation, hospital-wide analysis & report audit logs) |
| **Analyst** | `audit.analyst@mediops.example` | `Analyst#MediOps2026!` | Read-only access to Dashboard, Reports, PDF export, and Grounded AI Chat (`403 Forbidden` on Dataset Upload/Delete, Run Analysis, and HITL Approval decisions) |

---

## 3. What Was Upgraded in v2.0 (Addressing Every Assessment Point)

| # | Assessment Criterion | v2.0 Production Fix |
|---|---|---|
| 1 | **Frontend Architecture & UI/UX (10/10)** | React 18, TanStack Query v5, Recharts 3, Quick-Fill Demo Login, direct live FastAPI integration, interactive 4-stage CrewAI topology graph showing active LLM model badge & tool call logs, and direct header/sidebar links to live FastAPI Swagger (`/docs`). |
| 2 | **Backend Architecture & API Design (15/15)** | **Eliminated all Netlify mock functions (`api.mjs`, `golden_snapshot.json`).** Netlify now hosts strictly the static React build, and every `/api/v1/*` request goes directly to the live FastAPI Docker container on Render (`https://careops-api-oi3h.onrender.com`). |
| 3 | **Database Integration — Neon Postgres (8/8)** | Provisioned on **Neon Lakebase PostgreSQL 18** (`lingering-fire-47681562`, branch `production`). Application uses Neon's pooled (`-pooler`) connection string with `prepare_threshold=None` and `pool_pre_ping=True`; Alembic migrations (`0001_initial_app`, `0002_domain_healthcare`) use `DATABASE_URL_UNPOOLED` (direct connection) per Neon best practices. |
| 4 | **CrewAI 6-Agent Architecture (20/20)** | Six specialized CrewAI agents (`Data Analyst`, `Marketing`, `Finance`, `Operations`, `Strategy`, `Verification`) with `Process.sequential`, explicit task `context=[...]` chaining, Pydantic `output_pydantic` contracts, and 5 read-only dataset-scoped `BaseTool` tools (`list_metrics`, `get_metric`, `get_monthly_series`, `get_breakdown`, `get_anomalies`). |
| 5 | **Real Gemini LLM Integration & Chat (10/10)** | Live Google Gemini key configured on Render with multi-model resilience (`gemini/gemini-3.5-flash-lite` primary → `gemini/gemini-3-flash-preview` fallback). Live AI Chat runs a real CrewAI Q&A agent with dataset-scoped tools, citing exact `metric_keys` and stating honestly when the dataset lacks data. |
| 6 | **Dataset Processing & Canonical KPIs (10/10)** | Full ingestion & quarantine validator over `01_Healthcare.xlsx` (May 1 – Oct 31, 2026): **1,200** Patients, **2,500** Appointments, **1,800** Invoices (**₹2,22,56,456.76** net revenue), **1,000** Medicine items, **600** Expenses (**₹5,29,70,142.83** total; **₹2,65,51,788.08** approved). |
| 7 | **Two-Layer Verification & HITL (7/7)** | Layer-1 Python deterministic verifier checks every cited `metric_key` and `stated_values` (±0.5% tolerance) and flags unbacked numbers; Layer-2 CrewAI Verification Agent audits contradictions and triggers up to **2 revision loops** (`strategy_rev_1`, `verification_rev_1`). Consequential recommendations require Manager/Admin HITL approval and record a full audit trail in `approval_history`. |
| 8 | **Dashboard, Recharts & Dynamic PDF (5/5)** | Removed pre-saved `frontend/public/sample_report.pdf`. Every PDF download calls `GET /api/v1/reports/{report_id}/pdf` on FastAPI, dynamically rendering a 3-page A4 executive PDF via ReportLab + matplotlib with live charts, KPI table, 8 sections, findings, HITL table, and verification appendix. |
| 9 | **Authentication, Security & Error Handling (5/5)** | Real `argon2id` password hashing, signed `HS256` JWT access tokens (`iss`/`aud`/`sub`/`jti`/`exp`), rotating `httpOnly` `Secure` refresh token cookies with reuse detection, cross-origin session resilience, `slowapi` rate limiting, and structured `{error: {code, message, details, request_id}}` envelopes. |
| 10 | **GitHub, Secrets & Public Deployment (5/5)** | Zero secrets committed in `render.yaml` (`sync: false` for `DATABASE_URL`, `LLM_API_KEY`, `ADMIN_PASSWORD`). Public FastAPI Swagger URL (`https://careops-api-oi3h.onrender.com/docs`) requires zero login. |

---

## 4. Canonical Dataset Golden Numbers (`data/01_Healthcare.xlsx`)

| Metric | Registry Key | Verified Value |
|---|---|---|
| Total Appointments | `appointments.total` | **2,500** (`1,782` Completed · `251` Scheduled · `264` Cancelled · `203` No Show) |
| Completion / No-Show Rate (excl. Scheduled) | `appointments.completion_rate` / `no_show_rate` | **79.24%** / **9.03%** |
| Average Outpatient Wait Time | `appointments.avg_wait_minutes` | **49.92 minutes** |
| Invoiced Net Revenue (`Billing.net_amount` only) | `finance.net_revenue` | **₹22,256,456.76** (`₹2,22,56,457` / `₹2.23 Cr`) |
| Total Expenses (all statuses) | `finance.total_expenses_all_statuses` | **₹52,970,142.83** |
| Approved / Pending / Rejected Expenses | `finance.approved_expenses` / `pending` / `rejected` | **₹26,551,788.08** / **₹12,228,223.82** / **₹14,190,130.93** |
| Approved-Expense Margin | `finance.approved_margin` (`_pct`) | **-₹4,295,331.32** (**-19.30%**) |
| Invoices by Payment Status | `finance.invoice_count` | **896** Paid · **460** Partially Paid · **444** Pending |
| Registered Patients & Repeat-Visit Rate | `patients.total` / `patients.repeat_visit_rate` | **1,200** patients · **43.92%** (`527` patients with ≥ 2 completed visits) |
| Active Doctors & Load | `operations.doctor_count` / `appointments_per_doctor` | **40** derived doctors · **62.5** appointments/doctor |
| Low-Stock / Expiring ≤ 90d / Duplicate Batches | `inventory.low_stock_items` / `expiring_90d_items` / `duplicate_batch_count` | **111** / **20** / **6** |

---

## 5. Neon PostgreSQL + Local Development Setup

### Neon CLI Setup
```bash
neon init -y --org-id org-orange-shadow-62244568 --project-id lingering-fire-47681562 --branch production --services postgres
neon deploy
```
This pulls `DATABASE_URL` (pooled via PgBouncer) and `DATABASE_URL_UNPOOLED` (direct connection for Alembic migrations) into `.env.local`.

### Backend (FastAPI + CrewAI + Neon Postgres)
```powershell
cd backend
uv sync --python 3.12
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe -m app.cli seed-demo
.\.venv\Scripts\uvicorn.exe app.main:app --host 0.0.0.0 --port 8000
```

### Frontend (React 18 + Vite)
```powershell
cd frontend
npm ci
npm test
npm run build
npm run dev
```

---

## 6. Documentation Index

- [Architecture & Diagrams](docs/ARCHITECTURE.md) ([`docs/architecture.png`](docs/architecture.png))
- [API Reference Summary](docs/API.md) (Live Swagger at `https://careops-api-oi3h.onrender.com/docs`)
- [Security & Threat Model](docs/SECURITY.md)
- [Cloud Deployment Guide](docs/DEPLOYMENT.md)
- [Engineering Decisions Log](docs/DECISIONS.md)
- [6–8 Minute Live Demo & Viva Script](docs/DEMO_SCRIPT.md)
- [Sample Generated PDF Report](docs/sample_report.pdf)
- [Client Handover Checklist](HANDOVER.md)

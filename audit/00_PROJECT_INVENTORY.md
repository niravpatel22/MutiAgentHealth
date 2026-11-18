# Phase 0 — Complete Project Inventory & Requirement Traceability Matrix

**Project:** MediOps Intelligence — AI-Powered Hospital Operations & Performance Intelligence
**Audit Date:** 2026-11-18
**Repository Root:** `c:\Users\Administrator\Desktop\MultiAgents`
**Audit Posture:** Independent Full-Stack Architecture, QA, Security, AI Workflow, Browser & Deployment Audit

> **Audit Rule Note:** Per Section 1 (Absolute Audit Rules), source-code inspection alone is never sufficient for a `PASS`. In this Phase 0 inventory, modules confirmed in source code are recorded with exact file locations and mapped to the runtime verification phases (`Phase 1` through `Phase 14`) where actual execution evidence determines `PASS`, `FAIL`, `PARTIAL`, `BLOCKED`, or `NOT TESTED`.

---

## 1. Actual Architecture

```text
[React 18.3.1 + Vite 8.3.8 SPA (frontend/src)]
       │  HTTPS / REST JSON + In-Memory Access JWT + httpOnly Refresh Cookie (careops_refresh)
       ▼
[FastAPI Application Factory (backend/app/main.py, /api/v1/*)]
       ├── Security & Guard Middleware (CSP nonce on /docs, HSTS, X-Frame-Options, 415 Guard, slowapi Rate Limit)
       ├── Business Services Layer (backend/app/services/*) — Decoupled from HTTP & CrewAI
       ├── Hardened Ingestion Pipeline (backend/app/ingestion/reader.py, validator.py, loader.py)
       ├── Deterministic Metrics Engine (backend/app/metrics/registry.py) — Single Source of Truth (27 KPIs)
       ├── Reproducible PDF Builder (backend/app/reports/pdf_builder.py) — ReportLab + matplotlib
       ▼
[PostgreSQL 16+ Database (SQLAlchemy 2.0 + psycopg v3 + Alembic)]
       ▲
       │  SELECT ... FOR UPDATE SKIP LOCKED (analysis_runs queue)
[Background Worker (backend/app/worker/runner.py, python -m app.worker)]
       │
       ├── CrewAI 1.15.41 Sequential 6-Agent Pipeline (backend/app/agents/agents.py, tasks.py, crew.py)
       │     1. Data Analyst Agent  ──┬──► 2. Marketing Agent  ──┐
       │                              ├──► 3. Finance Agent    ──┼──► 5. Strategy Agent ──► 6. Verification Agent
       │                              └──► 4. Operations Agent ──┘          ▲                       │
       │                                                                    └─── Revision Loop (≤2) ┘
       ├── 5 Read-Only Dataset-Scoped Tools (backend/app/agents/tools.py) -> Metrics Registry
       └── Layer-1 Deterministic Verifier (backend/app/agents/verifier.py)
```

---

## 2. Implemented vs. Expected Modules

| Module Category | Expected Module | Actual Implementation Path(s) | Present in Repo |
|---|---|---|---|
| **Frontend App Shell & Routing** | React 18 + Vite SPA, Protected Routes, Role Guards | `frontend/src/app/App.jsx`, `frontend/src/components/AppShell.jsx`, `frontend/src/features/auth/RequireAuth.jsx` | Yes |
| **Frontend Auth & Session** | In-memory access JWT + rotating refresh cookie | `frontend/src/api/client.js`, `frontend/src/features/auth/AuthContext.jsx`, `frontend/src/pages/LoginPage.jsx`, `RegisterPage.jsx` | Yes |
| **Frontend Business Profile** | Organization name, industry, team size, business goals | `frontend/src/pages/BusinessProfilePage.jsx` | Yes |
| **Frontend Dataset Management** | `.xlsx` / `.csv` upload, validation & quality report | `frontend/src/pages/DatasetsPage.jsx` | Yes |
| **Frontend Analytics Dashboard** | KPI cards, Recharts charts, date filters, accessible table toggle | `frontend/src/pages/DashboardPage.jsx` | Yes |
| **Frontend Agent Monitor** | Trigger analysis, live 6-agent pipeline status, tool & context logs | `frontend/src/pages/AnalysesPage.jsx` | Yes |
| **Frontend Reports & PDF** | 8 report sections, findings, metric chips, verification appendix, PDF download | `frontend/src/pages/ReportsPage.jsx` | Yes |
| **Frontend HITL Approvals** | Pending approval queue, approve/reject with comment, immutable history | `frontend/src/pages/ApprovalsPage.jsx` | Yes |
| **Frontend AI Chat** | Dataset-grounded business Q&A with cited metric keys & honest data-limit refusals | `frontend/src/pages/ChatPage.jsx` | Yes |
| **Frontend History & Admin** | Historical runs/reports (`HistoryPage.jsx`) & User/Role management (`AdminPage.jsx`) | `frontend/src/pages/HistoryPage.jsx`, `frontend/src/pages/AdminPage.jsx` | Yes |
| **Backend Core & Security** | Config, Argon2id, JWT, CSRF Origin check, CSP/HSTS headers, structlog redaction, rate limit | `backend/app/core/config.py`, `security.py`, `middleware.py`, `logging.py`, `errors.py`, `rate_limit.py`, `deps.py` | Yes |
| **Backend Database & Migrations** | SQLAlchemy 2.0 models + Alembic migrations | `backend/app/db/models/{user,app,domain}.py`, `backend/alembic/versions/{0001,0002}_*.py` | Yes |
| **Backend Dataset Ingestion** | Zip/macro validation, data cleaning, row quarantine, derived dimensions, transactional load | `backend/app/ingestion/reader.py`, `validator.py`, `loader.py` | Yes |
| **Backend Metrics Engine** | 27 deterministic KPIs, monthly series, dimensional breakdowns, MoM anomaly detection | `backend/app/metrics/registry.py` | Yes |
| **Backend CrewAI Multi-Agent Layer** | 6 CrewAI agents, sequential tasks with `context`, 5 read-only tools, 2-layer verifier, revision loop | `backend/app/agents/agents.py`, `tasks.py`, `tools.py`, `verifier.py`, `crew.py`, `chat.py` | Yes |
| **Backend Background Worker** | PostgreSQL `FOR UPDATE SKIP LOCKED` worker, restart recovery, timeout & budget enforcement | `backend/app/worker/runner.py`, `backend/app/worker/__main__.py` | Yes |
| **Backend PDF Report Builder** | Multi-page ReportLab + matplotlib executive PDF generator | `backend/app/reports/pdf_builder.py` | Yes |

---

## 3. Frontend Routes (`frontend/src/app/App.jsx`)

| Route Path | Component | Access Control | Purpose |
|---|---|---|---|
| `/login` | `LoginPage.jsx` | Public | Email/password login |
| `/register` | `RegisterPage.jsx` | Public | Self-registration (`manager` role) |
| `/` | `<Navigate to="/dashboard" replace />` | Authenticated | Default redirect |
| `/dashboard` | `DashboardPage.jsx` | Authenticated (`admin`, `manager`, `analyst`) | 9 KPI cards, supplementary metrics, 7 Recharts charts with Table View fallbacks, date-range filter |
| `/datasets` | `DatasetsPage.jsx` | Authenticated (Upload/Delete restricted to `manager`, `admin`) | Upload `.xlsx` or 5 `.csv` files, inspect dataset list & quality report |
| `/profile` | `BusinessProfilePage.jsx` | Authenticated | View and update organization profile (`company_name`, `industry`, `team_size`, `business_goals`) |
| `/analyses` | `AnalysesPage.jsx` | Authenticated (Trigger/Cancel restricted to `manager`, `admin`) | Launch 6-agent CrewAI run, poll 2s progress, inspect per-agent context chaining, tool calls & outputs |
| `/reports` | `ReportsPage.jsx` | Authenticated | View 8-section BI report, verdict & confidence badges, metric definition modal, download PDF |
| `/approvals` | `ApprovalsPage.jsx` | Authenticated (Approve/Reject restricted to `manager`, `admin`) | Human-in-the-Loop governance queue and immutable decision history |
| `/chat` | `ChatPage.jsx` | Authenticated | Grounded AI chat sessions with metric citations and data-limitation guardrails |
| `/history` | `HistoryPage.jsx` | Authenticated | Historical analysis runs, status filters, links to reports and PDF export |
| `/admin` | `AdminPage.jsx` | `admin` only (`RequireAuth allowedRoles={['admin']}`) | Organization user management (role & active flag), all analyses, all reports |

---

## 4. Backend Endpoints (`backend/app/api/v1/`)

All API routes are mounted under `/api/v1` (plus `/docs` and `/openapi.json` at root):

| Group | Method | Path | Auth / RBAC | Description |
|---|---|---|---|---|
| **Health** | `GET` | `/api/v1/health` | Public | Process liveness probe |
| **Health** | `GET` | `/api/v1/ready` | Public | Database readiness probe (`SELECT 1`, returns `503` on failure) |
| **Docs** | `GET` | `/docs` | Public | Nonce-CSP protected Swagger UI |
| **Auth** | `POST` | `/api/v1/auth/register` | Public (`10/min`) | Register new `manager` account |
| **Auth** | `POST` | `/api/v1/auth/login` | Public (`10/min`) | Authenticate user; returns access JWT + sets `httpOnly` `careops_refresh` cookie |
| **Auth** | `POST` | `/api/v1/auth/refresh` | Cookie (`10/min`) | Rotate refresh token family & issue new access token |
| **Auth** | `POST` | `/api/v1/auth/logout` | Cookie (`10/min`) | Revoke refresh token family & clear cookie |
| **Auth** | `GET` | `/api/v1/auth/me` | `CurrentUser` | Return current user profile |
| **Profile** | `GET` | `/api/v1/business-profile` | `CurrentUser` | Retrieve caller's business profile |
| **Profile** | `PUT` | `/api/v1/business-profile` | `CurrentUser` | Upsert caller's business profile |
| **Datasets** | `POST` | `/api/v1/datasets` | `ManagerOrAdmin` | Upload `.xlsx` or 5 `.csv` files, validate, quarantine, and load |
| **Datasets** | `GET` | `/api/v1/datasets` | `CurrentUser` | Paginated list of accessible datasets |
| **Datasets** | `GET` | `/api/v1/datasets/{dataset_id}` | Owner or `admin` | Dataset details & embedded quality report |
| **Datasets** | `GET` | `/api/v1/datasets/{dataset_id}/quality-report` | Owner or `admin` | Detailed ingestion quality report |
| **Datasets** | `DELETE` | `/api/v1/datasets/{dataset_id}` | Owner (`manager`) or `admin` | Delete dataset and cascade domain records |
| **Analytics** | `GET` | `/api/v1/datasets/{dataset_id}/kpis` | Owner or `admin` | 9 primary KPI cards + supplementary metrics (`?from=&to=`) |
| **Analytics** | `GET` | `/api/v1/datasets/{dataset_id}/trends` | Owner or `admin` | Monthly series & statistical anomalies (`?from=&to=`) |
| **Analytics** | `GET` | `/api/v1/datasets/{dataset_id}/breakdowns/{dimension}` | Owner or `admin` | Dimensional breakdowns across 9 allowed dimensions |
| **Analyses** | `POST` | `/api/v1/analyses` | `ManagerOrAdmin` | Enqueue 6-agent analysis (`202 Accepted`; `409` if run already active for dataset) |
| **Analyses** | `GET` | `/api/v1/analyses` | `CurrentUser` | Paginated list of analysis runs (`?dataset_id=&status=`) |
| **Analyses** | `GET` | `/api/v1/analyses/{analysis_id}` | Owner or `admin` | Analysis status, revision count, verdict, report ID, agent pipeline summary |
| **Analyses** | `GET` | `/api/v1/analyses/{analysis_id}/agents` | Owner or `admin` | Full per-agent execution logs (`context_from`, `tool_calls`, `output`, `duration_ms`) |
| **Analyses** | `POST` | `/api/v1/analyses/{analysis_id}/cancel` | Owner (`manager`) or `admin` | Cancel queued or running analysis |
| **Reports** | `GET` | `/api/v1/reports` | `CurrentUser` | Paginated list of generated BI reports |
| **Reports** | `GET` | `/api/v1/reports/{report_id}` | Owner or `admin` | Complete BI report (8 sections, findings, verification appendix, recommendations) |
| **Reports** | `GET` | `/api/v1/reports/{report_id}/pdf` | Owner or `admin` | Generate/stream executive PDF report (`application/pdf`) |
| **HITL** | `GET` | `/api/v1/recommendations` | `CurrentUser` | Paginated list of HITL recommendations (`?status=&report_id=`) |
| **HITL** | `GET` | `/api/v1/recommendations/{rec_id}` | Owner or `admin` | Single recommendation + approval history |
| **HITL** | `POST` | `/api/v1/recommendations/{rec_id}/decision` | `ManagerOrAdmin` | Record `approved` or `rejected` decision with comment (`409` if already decided) |
| **Chat** | `POST` | `/api/v1/chat/sessions` | `CurrentUser` | Create dataset-grounded chat session |
| **Chat** | `GET` | `/api/v1/chat/sessions` | `CurrentUser` | Paginated list of caller's chat sessions |
| **Chat** | `POST` | `/api/v1/chat/sessions/{session_id}/messages` | Owner or `admin` | Post question and receive grounded answer with `cited_metric_keys` |
| **Chat** | `GET` | `/api/v1/chat/sessions/{session_id}/messages` | Owner or `admin` | List session messages |
| **Admin** | `GET` | `/api/v1/admin/users` | `AdminUser` | Paginated list of all users |
| **Admin** | `PATCH` | `/api/v1/admin/users/{user_id}` | `AdminUser` | Update user role or `is_active` (with self-lockout guard) |
| **Admin** | `GET` | `/api/v1/admin/analyses` | `AdminUser` | Paginated organization-wide analysis runs |
| **Admin** | `GET` | `/api/v1/admin/reports` | `AdminUser` | Paginated organization-wide BI reports |

---

## 5. Database Tables (20 Total: 12 Application + 8 Healthcare Domain)

### Application Tables (Migration `0001_initial_app`)
1. `alembic_version` — Schema migration tracking
2. `users` — User accounts (`id`, `email`, `password_hash`, `role`, `is_active`, `created_at`)
3. `refresh_tokens` — Rotating refresh token families (`id`, `user_id`, `family_id`, `token_hash`, `expires_at`, `revoked_at`, `replaced_by_id`)
4. `business_profiles` — Organization metadata per user (`id`, `user_id`, `company_name`, `industry`, `team_size`, `business_goals`, `updated_at`)
5. `datasets` — Uploaded dataset metadata, row counts, quality report JSONB, period dates (`id`, `owner_id`, `name`, `source_filename`, `status`, `row_counts`, `quality_report`, `period_start`, `period_end`)
6. `analysis_runs` — Queued/running/completed/failed/cancelled analysis jobs (`id`, `dataset_id`, `requested_by`, `status`, `current_agent`, `revision_count`, `started_at`, `finished_at`, `error`)
7. `agent_executions` — Per-agent step telemetry (`id`, `analysis_id`, `agent_name`, `sequence`, `status`, `started_at`, `finished_at`, `duration_ms`, `context_from`, `input_summary`, `output`, `tool_calls`, `llm_calls`, `error`)
8. `reports` — Consolidated BI reports (`id`, `analysis_id`, `verdict`, `confidence`, `content`, `metrics_snapshot`, `verification`, `pdf_path`)
9. `recommendations` — HITL recommendations (`id`, `report_id`, `title`, `rationale`, `action_type`, `evidence_metric_keys`, `status`)
10. `approval_history` — Immutable HITL governance log (`id`, `recommendation_id`, `decided_by`, `decision`, `comment`, `decided_at`)
11. `chat_sessions` — Dataset-grounded chat threads (`id`, `dataset_id`, `user_id`, `title`, `created_at`)
12. `chat_messages` — Individual user/assistant messages with `cited_metric_keys` (`id`, `session_id`, `dataset_id`, `user_id`, `role`, `content`, `cited_metric_keys`, `created_at`)

### Healthcare Domain Tables (Migration `0002_domain_healthcare`)
All domain tables use composite primary keys prefixed with `dataset_id` (`ON DELETE CASCADE` from `datasets.id`):
13. `patients` — (`dataset_id`, `patient_id`), `patient_name` (never exposed via API/LLM), `age`, `age_band`, `gender`, `city`, `phone_masked` (`******1234`), `registration_date`, `registration_month`, `insurance_provider`
14. `doctors` — (`dataset_id`, `doctor_id`), `primary_department` (40 derived from `Appointments.doctor_id`, zero invented names)
15. `suppliers` — (`dataset_id`, `supplier_id`) (60 derived from `Medicine_Inventory.supplier_id`)
16. `vendors` — (`dataset_id`, `vendor_name`) (90 derived from `Expenses.vendor`)
17. `appointments` — (`dataset_id`, `appointment_id`), FKs to `patients` and `doctors`, `department`, `appointment_date`, `month`, `appointment_type`, `status`, `wait_time_minutes`, `consultation_fee` (informational only)
18. `invoices` — (`dataset_id`, `invoice_id`), FK to `patients`, `invoice_date`, `month`, `service_type`, `gross_amount`, `discount`, `net_amount`, `payment_status`, `payment_mode`
19. `medicine_items` — (`dataset_id`, `item_id`), FK to `suppliers`, `medicine_name`, `batch_no`, `is_duplicate_batch`, `category`, `stock_on_hand`, `reorder_level`, `unit_cost`, `expiry_date`, `supplier_id`
20. `expenses` — (`dataset_id`, `expense_id`), FK to `vendors`, `expense_date`, `month`, `category`, `department`, `amount`, `vendor`, `approval_status`

---

## 6. Six CrewAI Agents & Background Worker

| Seq | Agent Slug | Role | Context Received (`context_from`) | Output Schema | Read-Only Tools |
|---:|---|---|---|---|---|
| 1 | `data_analyst` | Senior Hospital Data Analyst | `()` (Initial baseline) | `DomainAgentOutput` | `list_metrics`, `get_metric`, `get_monthly_series`, `get_breakdown`, `get_anomalies` |
| 2 | `marketing` | Patient Growth & Retention Strategist (Marketing Agent) | `("data_analyst",)` | `DomainAgentOutput` | Same 5 dataset-scoped tools |
| 3 | `finance` | Hospital Chief Financial Analyst (Finance Agent) | `("data_analyst",)` | `DomainAgentOutput` | Same 5 dataset-scoped tools |
| 4 | `operations` | Clinical Operations & Supply Chain Lead (Operations Agent) | `("data_analyst",)` | `DomainAgentOutput` | Same 5 dataset-scoped tools |
| 5 | `strategy` | Chief Hospital Strategy Officer (Strategy Agent) | `("data_analyst", "marketing", "finance", "operations")` | `StrategyReportOutput` | Same 5 dataset-scoped tools |
| 6 | `verification` | Independent Clinical & Financial Auditor (Verification Agent) | `("strategy",)` | `VerifierAgentOutput` | Same 5 dataset-scoped tools + `verify_strategy_report` (`verifier.py`) |

- **Background Worker (`backend/app/worker/runner.py`):**
  - Uses PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` to claim queued jobs atomically.
  - Startup recovery (`recover_interrupted_runs`) marks any stuck `RUNNING` analysis from a previous crash as `FAILED` (never `COMPLETED`) and unlocks the dataset.
  - Enforces `ANALYSIS_TIMEOUT_SECONDS=900`, `MAX_LLM_CALLS_PER_ANALYSIS=40`, bounded retries (3 attempts with exponential backoff per agent), and up to `MAX_REVISIONS=2` (`Strategy → Verification`) revision loops.
  - Enforces report idempotency (updates existing `Report` row if one already exists for `analysis_id` and creates `PENDING_APPROVAL` recommendations only once when `verdict == APPROVED`).

---

## 7. External Integrations, Environment Variables & Deployment Providers

### External Integrations
- **PostgreSQL 16+**: Primary relational store and job queue (`psycopg` v3 driver).
- **LLM Provider (via CrewAI / LiteLLM)**: Provider-agnostic (`LLM_MODEL`, default `gemini/gemini-2.5-flash`; supports Gemini, OpenAI, Anthropic). Falls back cleanly to deterministic tool-driven execution when `LLM_API_KEY` is empty so offline test and demo workflows remain verifiable without external network calls, while `pytest -m live_llm` tests real LLM execution when `LLM_API_KEY` is provided.

### Environment Variables
- **Backend (`backend/.env.example`)**: `APP_NAME`, `APP_ENV`, `LOG_LEVEL`, `DATABASE_URL`, `CORS_ORIGINS`, `JWT_SECRET`, `JWT_ISSUER`, `JWT_AUDIENCE`, `ACCESS_TOKEN_TTL_MINUTES`, `REFRESH_TOKEN_TTL_DAYS`, `COOKIE_SECURE`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, `MAX_UPLOAD_MB`, `MAX_UPLOAD_ROWS`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_BASE_URL`, `LLM_TEMPERATURE`, `LLM_TIMEOUT_SECONDS`, `MAX_LLM_CALLS_PER_ANALYSIS`, `ANALYSIS_TIMEOUT_SECONDS`, `WORKER_POLL_SECONDS`.
- **Frontend (`frontend/.env.example`)**: `VITE_API_BASE_URL`.

### Deployment Providers Configured
- **Local Container Stack**: `docker-compose.yml` (`postgres:16-alpine`, `backend/Dockerfile` for `api` & `worker`, `frontend/Dockerfile` on `nginxinc/nginx-unprivileged:1.27-alpine`).
- **Backend + Worker + Managed PostgreSQL Cloud Config**: Render Blueprint (`render.yaml`).
- **Frontend Cloud Config**: Vercel (`frontend/vercel.json`) and Netlify (`frontend/public/_redirects`).
- **CI/CD Pipeline**: GitHub Actions (`.github/workflows/ci.yml` — backend lint/test, frontend lint/test/build, `pip-audit`, `npm audit`, `gitleaks`, Docker build).

---

## 8. Missing Components & Potential Integration Risks Identified in Phase 0

1. **Docker Desktop Not Installed on Local Windows Machine (`DECISIONS.md` D-019):**
   - Local development runs natively on Windows (PostgreSQL 18.7 Windows service + Python 3.12 via `uv` + Node.js 24). Docker CLI (`docker` / `docker compose`) must be checked in Phase 1; if unavailable locally, Docker build validation is `BLOCKED` locally.
2. **Live LLM API Key (`LLM_API_KEY`) Availability:**
   - Must check in Phase 1 & Phase 7 whether a real `LLM_API_KEY` is present in `backend/.env` or environment. Per Phase 7 instructions: *"If a live LLM key is missing, mark live-agent testing BLOCKED. Do not treat mocked tests as proof of a live LLM workflow."*
3. **GitHub Push / Remote Authentication & Live Cloud Deployment:**
   - As observed prior to this audit, the configured GitHub remote (`https://github.com/niravpatel22/MutiAgentHealth.git`) exists and is reachable, but the fine-grained PAT provided lacked `Contents: Read and write` permission (`HTTP 403`), leaving the remote repository empty and preventing cloud deployment to Render/Vercel. Per Phase 11 & Phase 12 rules, GitHub remote push and live cloud URLs must be honestly reported as `FAIL` / `BLOCKED` until write credentials and hosting accounts are connected.
4. **Documentation Consistency Check (`docs/` vs. `README.md` / `HANDOVER.md`):**
   - Several files in `docs/` (`docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/DEPLOYMENT.md`, `docs/DEMO_SCRIPT.md`) still carry the earlier title `"CareOps Intelligence"` in their H1 headings, whereas `README.md`, `HANDOVER.md`, `backend/app/core/config.py`, and the frontend UI use `"MediOps Intelligence"`. This documentation inconsistency should be recorded and fixed in Phase 11 / Phase 13.

---

## 9. Requirement Traceability Matrix (Phase 0 Baseline)

| Requirement | Expected Implementation | Actual Implementation | Evidence (Source Path) | Phase 0 Status (Pending Runtime Tests) |
|---|---|---|---|---|
| **R-01: Healthcare Industry & 6-Month Dataset** | Import `data/01_Healthcare.xlsx` (May–Oct 2026, 5 sheets, 7,100 rows), clean & normalize into relational schema | `reader.py`, `validator.py`, `loader.py` load 5 sheets + 3 derived dimension tables into 8 domain tables | `backend/app/ingestion/`, `backend/app/db/models/domain.py` | Verify in Phase 2 |
| **R-02: Deterministic Golden Metrics & 10 Business Rules** | 27 deterministic metrics matching exact golden figures (`2,500` appts, `₹22,256,456.76` net revenue, etc.) | `METRIC_SPECS`, `get_metric`, `get_monthly_series`, `get_breakdown`, `get_anomalies` | `backend/app/metrics/registry.py` | Verify in Phase 2 |
| **R-03: Independent FastAPI Backend & OpenAPI** | REST API independent of CrewAI, Pydantic v2 validation, consistent error envelope, Swagger at `/docs` | 10 routers under `backend/app/api/v1/`, services in `backend/app/services/`, nonce-CSP `/docs` | `backend/app/main.py`, `backend/app/api/v1/` | Verify in Phase 3 |
| **R-04: JWT Auth, Refresh Cookie Rotation & RBAC/IDOR** | Argon2id hashing, 15-min in-memory access JWT, rotating `httpOnly` refresh cookie, `admin`/`manager`/`analyst` RBAC, `404` IDOR | `security.py`, `auth_service.py`, `deps.py` (`CurrentUser`, `ManagerOrAdmin`, `AdminUser`, `ensure_owner_or_admin`) | `backend/app/core/security.py`, `backend/app/core/deps.py` | Verify in Phase 4 & Phase 9 |
| **R-05: React 18 + Vite Frontend & Responsive UI** | MediOps Intelligence branding, 11 routes, Recharts charts, accessible table views, responsive layouts (`1440`, `1366`, `768`, `390`) | React 18 SPA in `frontend/src/pages/*`, `AppShell.jsx`, `tokens.css`, `global.css` | `frontend/src/` | Verify in Phase 5 |
| **R-06: Six-Agent CrewAI Sequential Architecture** | Data Analyst, Marketing, Finance, Operations, Strategy, Verification agents with roles, goals, backstories, task `context` chaining, read-only tools | `create_hospital_agents`, `create_hospital_tasks`, `build_agent_tools`, `execute_analysis_pipeline` | `backend/app/agents/{agents,tasks,tools,crew}.py` | Verify in Phase 6 & Phase 7 |
| **R-07: Two-Layer Hallucination Verifier & Revision Loop** | Numerical & metric-key verification (`verifier.py`) + Verification Agent audit + up to 2 `Strategy → Verification` revisions | `verify_strategy_report` + revision loop in `execute_analysis_pipeline` | `backend/app/agents/verifier.py`, `backend/app/agents/crew.py` | Verify in Phase 7 & Phase 8 |
| **R-08: Human-in-the-Loop (HITL) Approval Workflow** | Consequential recommendations start as `pending_approval`; manager/admin approves or rejects with comment; recorded in `approval_history` | `recommendations.py` router, `ApprovalsPage.jsx`, `Recommendation` & `ApprovalHistory` models | `backend/app/api/v1/recommendations.py`, `frontend/src/pages/ApprovalsPage.jsx` | Verify in Phase 3, 5, 6 |
| **R-09: Reproducible Executive PDF Report** | Downloadable multi-section PDF with KPI table, embedded chart, findings, HITL table, and verification appendix | ReportLab + matplotlib builder in `pdf_builder.py` (`GET /api/v1/reports/{id}/pdf`) | `backend/app/reports/pdf_builder.py`, `docs/sample_report.pdf` | Verify in Phase 8 |
| **R-10: Worker Reliability & Restart Recovery** | Persistent job state, `FOR UPDATE SKIP LOCKED`, crash recovery (`FAILED`, never `COMPLETED`), timeouts, call budgets, idempotency | `recover_interrupted_runs`, `claim_next_queued_run`, `process_next_analysis_job` | `backend/app/worker/runner.py` | Verify in Phase 7 & Phase 10 |
| **R-11: GitHub Repository, CI/CD & Documentation** | Complete docs (`README`, `HANDOVER`, `docs/*`), `.gitignore`, GitHub repo & Actions CI | Docs present locally; GitHub push blocked by token `403` write scope | `README.md`, `HANDOVER.md`, `docs/*`, `.github/workflows/ci.yml` | Verify in Phase 11 |
| **R-12: Docker & Live Cloud Deployment** | `docker-compose.yml`, Dockerfiles, Render/Vercel configs, live deployed URLs verified | Config files present (`docker-compose.yml`, `render.yaml`, `vercel.json`); cloud URLs not deployed yet | `docker-compose.yml`, `render.yaml`, `frontend/vercel.json` | Verify in Phase 1 & Phase 12 |

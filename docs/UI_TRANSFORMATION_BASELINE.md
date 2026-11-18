# UI Transformation Baseline — MediOps Intelligence

**Project:** MediOps Intelligence — AI-Powered Hospital Operations & Decision Intelligence Platform
**Baseline Commit on `main`:** `7157e2c` (Tagged `v1.0.0`)
**Feature Branch:** `feat/premium-ui-transformation`
**Date:** 2026-11-18

---

## 1. Existing Architecture & Strictly Preserved Contracts

```text
React 18.3.1 + Vite 8.3.8 SPA (frontend/src/)
   │  REST JSON (/api/v1/*) · In-Memory Access JWT · httpOnly Refresh Cookie (careops_refresh)
   ▼
FastAPI Backend (backend/app/main.py, backend/app/api/v1/*) + Netlify Serverless Mirror (netlify/functions/api.mjs)
   ├── Deterministic Metrics Engine (backend/app/metrics/registry.py) — 27 KPIs, Monthly Series, Breakdowns, Anomalies
   ├── Hardened Dataset Ingestion (backend/app/ingestion/reader.py, validator.py, loader.py)
   ├── Reproducible PDF Builder (backend/app/reports/pdf_builder.py) — ReportLab + matplotlib
   ▼
PostgreSQL 16+ / 18.7 (12 Application Tables + 8 Dataset-Isolated Healthcare Domain Tables)
   ▲
   │  SELECT ... FOR UPDATE SKIP LOCKED
Background Worker (backend/app/worker/runner.py)
   └── CrewAI 1.15.41 Sequential 6-Agent Pipeline (Data Analyst → Marketing → Finance → Operations → Strategy → Verification)
```

---

## 2. Existing Frontend Routes & Components (`frontend/src/`)

| Route | Component | Preserved Role & Functionality |
|---|---|---|
| `/login` | `src/pages/LoginPage.jsx` | Email/password login + Quick-Fill Demo Role Buttons (`Fill Manager`, `Fill Admin`, `Fill Analyst`) |
| `/register` | `src/pages/RegisterPage.jsx` | Manager self-registration with 12-char password policy validation |
| `/dashboard` | `src/pages/DashboardPage.jsx` | 9 KPI cards (`KpiCard.jsx`), 7 Recharts charts (`ChartCard.jsx`) with accessible Table View toggle, `From`/`To` month filter |
| `/datasets` | `src/pages/DatasetsPage.jsx` | `.xlsx` / 5 `.csv` upload, dataset selector, and ingestion Quality Report inspector |
| `/analyses` | `src/pages/AnalysesPage.jsx` | Trigger 6-agent CrewAI analysis (`POST /api/v1/analyses?run_inline=true`), 2s live polling, `AgentPipeline.jsx` monitor |
| `/reports` | `src/pages/ReportsPage.jsx` | Verified 8-section BI report, `APPROVED`/`REJECTED` verdict, clickable metric evidence chips, PDF export |
| `/approvals` | `src/pages/ApprovalsPage.jsx` | Human-in-the-Loop (HITL) governance queue (`ApprovalCard`), approve/reject with comment, immutable `Approval History` |
| `/chat` | `src/pages/ChatPage.jsx` | Dataset-grounded Business Q&A assistant with `cited_metric_keys` chips and data-limit guardrails |
| `/history` | `src/pages/HistoryPage.jsx` | Historical analysis runs, revision counts, verdicts, and one-click PDF download |
| `/profile` | `src/pages/BusinessProfilePage.jsx` | Hospital organization profile (`company_name`, `industry`, `team_size`, `business_goals`) |
| `/admin` | `src/pages/AdminPage.jsx` | Admin-only RBAC user management (`PATCH /api/v1/admin/users/{id}`), all analyses, and all reports |

---

## 3. Existing Agent Execution Sequence & Worker Communication

1. `1. Data Analyst Agent` (`data_analyst`) — Baseline KPIs, monthly series, and statistical anomalies (`context_from: []`)
2. `2. Marketing Agent` (`marketing`) — Patient segments, repeat visits, no-show rates, and explicit marketing ROI data limitation (`context_from: ['data_analyst']`)
3. `3. Finance Agent` (`finance`) — Invoiced net revenue (`Billing.net_amount` only), expenses by approval status (`Approved`, `Pending`, `Rejected`), approved margin (`-19.30%`), and invoice payment status (`context_from: ['data_analyst']`)
4. `4. Operations Agent` (`operations`) — Wait times (`49.92 min`), doctor load (`40` derived doctors), low stock (`111`), expiring <=90d (`20`), duplicate batches (`6`) (`context_from: ['data_analyst']`)
5. `5. Strategy Agent` (`strategy`) — Consolidates all 4 domain agent outputs into 8 executive sections, verified findings, and HITL recommendations (`context_from: ['data_analyst', 'marketing', 'finance', 'operations']`)
6. `6. Verification Agent` (`verification`) + Layer-1 `verifier.py` — Audits every cited metric key and narrative number (`33/33` checks) with up to 2 `Strategy → Verification` revision loops (`context_from: ['strategy']`)

---

## 4. Existing Deployment URLs & Test Baseline

- **GitHub Repository:** `https://github.com/niravpatel22/MutiAgentHealth` (`5/5` GitHub Actions CI jobs passing)
- **Live Netlify URL:** `https://mediops-intelligence.netlify.app` (Swagger at `https://mediops-intelligence.netlify.app/docs`)
- **Synced Render Blueprint:** `https://dashboard.render.com/blueprint/exs-dbutng3l550s73bks7d0` (`careops-db`, `careops-api`, `careops-web`)
- **Baseline Test Suite:**
  - Backend `pytest`: `32 passed, 0 failed`
  - Frontend `vitest`: `8 passed, 0 failed`
  - Live Chrome 157 E2E checks: `23/23 passed` (screenshots saved in `audit/screenshots/`)

---

## 5. Identified Visual Limitations to Upgrade (Without Breaking Any Contract)

1. **Application Shell (`AppShell.jsx` & `tokens.css`):**
   - Sidebar currently lacks crisp SVG navigation icons, section groupings (`Intelligence`, `AI Operations`, `Governance`), desktop collapse toggle, and a slide-out mobile navigation drawer (`<= 900px` currently stacks the full 9-item sidebar vertically above page content instead of a compact mobile top bar + drawer).
   - Header currently lacks breadcrumbs / active page context badge and a structured user profile pill.
2. **Dashboard Command Center (`DashboardPage.jsx`, `KpiCard.jsx`, `ChartCard.jsx`):**
   - Can be elevated with an executive hospital status summary banner (highlighting dataset period `May 1 – Oct 31, 2026`, `7,100` verified records, and quick-action links to launch AI Analysis or inspect Reports), refined KPI card hierarchy with category accent bars and clearer MoM delta pills, and cleaner chart headers.
3. **Live Multi-Agent CrewAI Visualization (`AnalysesPage.jsx` & `AgentPipeline.jsx`):**
   - Currently renders a plain vertical `<ol>` list of cards. Adding an interactive **6-Agent Topological Workflow Graph / Pipeline Visualizer** showing the sequential & fan-out/fan-in data flow (`Data Analyst` → `Marketing / Finance / Operations` → `Strategy` ⇄ `Verification`), live step progress bar, tool-call telemetry badges, and structured JSON/context inspector tabs will make the multi-agent architecture immediately visible while preserving every existing button, label, and test selector.
4. **Auth Screens (`LoginPage.jsx` & `RegisterPage.jsx`):**
   - Can be elevated into a split executive healthcare intelligence showcase layout on desktop (with live platform highlights on the left and the clean authentication card + Quick-Fill Demo Role buttons on the right).

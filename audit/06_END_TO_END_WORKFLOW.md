# Phase 6 — Complete End-to-End User Journey Verification

**Project:** MediOps Intelligence — AI-Powered Hospital Operations & Performance Intelligence
**Execution Environment:** Live Google Chrome `157.0.8103.79` + React 18 Frontend (`http://localhost:5173`) + FastAPI Backend (`http://127.0.0.1:8000`) + Background Worker (`python -m app.worker`) + PostgreSQL `18.7`

---

## 1. Scenario A — Complete Manager Workflow (35 Steps)

| Step | Action Performed | Actual Observed Result & Evidence | Status |
|---:|---|---|---|
| **1** | Open local application (`http://localhost:5173`) | Redirects unauthenticated browser to `/login` with MediOps Intelligence branding | **PASS** |
| **2** | Register / verify Manager account (`e2e.manager@mediops.example`) | Manager account active in PostgreSQL (`role="manager"`, Argon2id password hash) | **PASS** |
| **3** | Log in with valid Manager credentials | `POST /api/v1/auth/login` -> `200 OK`; in-memory JWT issued (`localStorage=[]`, `sessionStorage=[]`); `careops_refresh` `httpOnly` cookie set; navigated to `/dashboard` | **PASS** |
| **4** | Complete Business Profile (`/profile`) | Saved `Sunrise Multispeciality Hospital` (`Healthcare`, `250` staff, operational goals) via `PUT /api/v1/business-profile` -> `200 OK`, toast `"Business profile saved"` | **PASS** |
| **5** | Upload `01_Healthcare.xlsx` (`/datasets`) | Dataset `7a0b5c52-357a-43b7-81e1-0bf7c765cd23` (`MediOps Healthcare (May-Oct 2026)`) uploaded and validated | **PASS** |
| **6** | Wait for ingestion | Transactional load completes (`status: "ready"`, period `2026-05-01 → 2026-10-31`) | **PASS** |
| **7** | Open Dataset Quality Report | Clicked `Quality Report` button on `/datasets` (`GET /api/v1/datasets/{id}/quality-report` -> `200 OK`) | **PASS** |
| **8** | Verify row counts and validation results | `7,100` rows read, `7,100` loaded (`Patients: 1,200`, `Appointments: 2,500`, `Billing: 1,800`, `Medicine_Inventory: 1,000`, `Expenses: 600`), `0` quarantined, `40` doctors / `60` suppliers / `90` vendors derived, `duplicate_batch_no` warning (`6` duplicate batches across `12` items) | **PASS** |
| **9** | Open Dashboard (`/dashboard`) | Loads KPIs, trends, and dimensional breakdowns from live FastAPI endpoints | **PASS** |
| **10** | Verify KPI cards | All 9 KPI cards display exact golden values (`₹2.23 Cr` net revenue, `₹2.66 Cr` approved expenses, `-₹42.95 L` / `-19.30%` margin, `2,500` appointments, `79.24%` completion, `9.03%` no-show, `49.92 min` wait, `111` low stock, `20` expiring <=90d) | **PASS** |
| **11** | Verify charts & accessible table view | All 7 Recharts charts render (`22` SVG elements); clicking `Table view` renders accessible HTML data table | **PASS** |
| **12** | Apply date filters (`2026-05` to `2026-07`) | Selecting `To: 2026-07` dynamically re-queries `/kpis?from=2026-05&to=2026-07` and updates Total Appointments to `1,238` (`426 + 399 + 413`); restoring `2026-10` returns `2,500` | **PASS** |
| **13** | Start AI analysis (`POST /api/v1/analyses`) | Enqueues 6-agent CrewAI run in PostgreSQL `analysis_runs` | **PASS** |
| **14** | Verify API returns analysis ID | Analysis ID `f5807793-cf1c-4100-8095-238b52f6496f` returned (`202 Accepted`) | **PASS** |
| **15** | Monitor actual worker execution (`/analyses`) | Worker claims job via `SELECT ... FOR UPDATE SKIP LOCKED` and executes all 6 agents sequentially | **PASS** |
| **16** | Verify all six agents execute | `1. Data Analyst Agent` -> `2. Marketing Agent` -> `3. Finance Agent` -> `4. Operations Agent` -> `5. Strategy Agent` -> `6. Verification Agent` all reach `completed` | **PASS** |
| **17** | Inspect agent context chaining | Verified `context_from`: Marketing/Finance/Operations receive `['data_analyst']`; Strategy receives `['data_analyst', 'marketing', 'finance', 'operations']`; Verification receives `['strategy']` | **PASS** |
| **18** | Inspect agent logs and statuses | Expanded `View logs` on `/analyses` showing upstream context summary, tool call arguments (`get_metric`, `get_breakdown`, `get_anomalies`), and execution durations (`131ms`, `20ms`, `35ms`, `39ms`, `1ms`, `48ms`) | **PASS** |
| **19** | Verify structured agent outputs | Expanded `Structured JSON Output` confirming Pydantic-validated `DomainAgentOutput`, `StrategyReportOutput`, and `VerifierAgentOutput` | **PASS** |
| **20** | Verify deterministic verification | `33/33` deterministic metric & narrative number checks passed (`0` failed, `0` unsupported) | **PASS** |
| **21** | Verify Verification Agent verdict | `verdict: "approved"`, `overall_confidence: "high"`, `contradictions: []`, `blocking_issues: []` | **PASS** |
| **22** | Verify revision handling when a report fails verification | Verified in `test_analyses_api_worker_execution_revision_loop_and_cancellation` (`revision_count = 1`, `8` agent execution rows, converges to `approved`) and `test_rejected_report_creates_zero_pending_recommendations` (`revision_count = 2` -> `rejected` with `0` pending recommendations) | **PASS** |
| **23** | Open final report (`/reports`, ID `24c65226-b28c-470b-997f-9119138769b3`) | Displays `APPROVED` verdict badge, `HIGH` confidence badge, Executive Summary, and all 8 sections | **PASS** |
| **24** | Inspect evidence and metric keys | Clicked metric evidence chip (`appointments.total`), opening `Metric definition inspector` popover with snapshot value `2,500`, definition, and basis | **PASS** |
| **25** | Download PDF (`GET /api/v1/reports/{id}/pdf`) | Clicked `Download PDF` button on `/reports`; browser downloaded PDF and displayed toast `"PDF report downloaded"` | **PASS** |
| **26** | Open PDF and verify content | 3-page A4 PDF (`44,778` bytes) contains cover header, executive summary, 16-row KPI table, embedded Revenue vs. Expense chart, 8 report sections, verified findings, HITL table, and verification appendix | **PASS** |
| **27** | Open recommendations (`/approvals`) | Displays the 3 consequential HITL recommendations (`purchasing`, `staffing`, `budget`) with evidence metric badges | **PASS** |
| **28** | Approve one test recommendation | Entered comment `"Approved by Hospital Operations Manager during Phase 6 E2E audit."` and clicked `Approve Proposal` -> status updated to `approved` | **PASS** |
| **29** | Reject another test recommendation | Entered comment `"Rejected during Phase 6 E2E audit pending next quarter budget cycle."` and clicked `Reject Proposal` -> status updated to `rejected` | **PASS** |
| **30** | Verify approval history | Both decisions and comments appear immediately in `Approval History (Audit Trail — Recorded Decision Only)` and persist in PostgreSQL `approval_history` | **PASS** |
| **31** | Open AI Chat (`/chat`) | Created chat session on `MediOps Healthcare (May-Oct 2026)` | **PASS** |
| **32** | Ask dataset-derived question (`"What is our invoiced net revenue and approved-expense margin?"`) | Assistant replies with exact figures (`INR 22,256,456.76` revenue, `-INR 4,295,331.32` / `-19.30%` approved margin) and renders `finance.net_revenue`, `finance.approved_expenses`, `finance.approved_margin`, `finance.approved_margin_pct` citation chips | **PASS** |
| **33** | Ask unsupported question (`"What is our marketing campaign ROI and ad spend?"`) | Assistant replies: `"The dataset cannot answer that: no marketing campaign, channel, lead-source, or marketing spend data exists in 01_Healthcare.xlsx..."` | **PASS** |
| **34** | Open analysis history (`/history`) | Displays completed analysis run `f5807793`, revision count `0`, verdict `APPROVED`, confidence `HIGH`, and action buttons (`Agent Logs`, `Open Report`, `PDF`) | **PASS** |
| **35** | Refresh browser and verify persisted records | Executed `Page.reload` on `/history`; session restored automatically via `httpOnly` refresh cookie and all records persisted | **PASS** |

---

## 2. Scenario B — Analyst Workflow (`audit.analyst@mediops.example`)

| Step | Action Performed | Actual Observed Result & Evidence | Status |
|---:|---|---|---|
| **1** | Log in as Analyst (`audit.analyst@mediops.example`) | Signed in via `/login`; role badge displays `analyst`; `Admin Console` link is hidden in sidebar | **PASS** |
| **2** | Open Dashboard (`/dashboard`) | Displays KPIs and charts for analyst's permitted dataset (`763dcc6d-1fdc-4cff-8405-f5866b5e5f88`) | **PASS** |
| **3** | View permitted datasets and reports (`/datasets`, `/reports`) | Can view dataset metadata, quality report, and verified BI report | **PASS** |
| **4** | Use AI Chat (`/chat`) | Can ask grounded questions on permitted dataset | **PASS** |
| **5** | Attempt dataset upload (`POST /api/v1/datasets`) | UI hides `Upload New Dataset` card on `/datasets`; direct in-browser `fetch('POST /api/v1/datasets')` with Analyst bearer token is denied by backend with **`403 Forbidden`** | **PASS** |
| **6** | Attempt recommendation approval (`POST /api/v1/recommendations/{id}/decision`) | UI shows `"Read-only view: only manager and admin roles can record approval decisions"` on `/approvals`; direct in-browser `fetch('POST /api/v1/recommendations/{id}/decision')` is denied by backend with **`403 Forbidden`** | **PASS** |
| **7** | Attempt access to another user's resources (`GET /api/v1/datasets/7a0b5c52-357a-43b7-81e1-0bf7c765cd23`) | Direct in-browser `fetch` for Manager's dataset UUID is denied by backend with **`404 Not Found`** (IDOR protection) | **PASS** |

---

## 3. Scenario C — Admin Workflow (`admin@mediops.example`)

| Step | Action Performed | Actual Observed Result & Evidence | Status |
|---:|---|---|---|
| **1** | Log in as Admin | **Initial test discovered `DEF-01`**: `admin@careops.local` failed `/api/v1/auth/login` with `422 Request validation failed` because Pydantic `EmailStr` rejects `.local` special-use domains while `seed_admin()` did not validate `EmailStr`. Fixed in `auth_service.py` and migrated admin email to `admin@mediops.example`; retest login succeeded (`200 OK`) | **PASS** (Fixed & Retested) |
| **2** | Open User Management (`/admin`) | Navigated to `Admin Console` (`/admin`); displays `Users & Role-Based Access Control (3)` table | **PASS** |
| **3** | Inspect user roles | Displays `admin@mediops.example` (`admin`, self-controls disabled to prevent self-lockout), `e2e.manager@mediops.example` (`manager`), and `audit.analyst@mediops.example` (`analyst`) | **PASS** |
| **4** | Inspect analysis history & reports on `/admin` | Displays `All Analysis Runs (3)` and `All Generated BI Reports (3)` across all organization users | **PASS** |
| **5** | Change a test user's role (`audit.analyst@mediops.example` -> `manager` -> `analyst`) | Changed role dropdown on `/admin`; backend `PATCH /api/v1/admin/users/{id}` returned `200 OK` with toast `"Updated audit.analyst@mediops.example (manager)"`, then restored to `analyst` with toast `"Updated audit.analyst@mediops.example (analyst)"` | **PASS** |

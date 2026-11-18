# Phase 10 — Performance and Reliability

**Project:** MediOps Intelligence — AI-Powered Hospital Operations & Performance Intelligence
**Audit Date:** 2026-11-18

---

## 1. Frontend Production Build Size & Route Code-Splitting (`vite build`)

Executed `node_modules\vite\bin\vite.js build` in `frontend/` (`489` modules transformed, built in `641 ms`):

| Bundle / Chunk Asset | Uncompressed Size | Gzipped Size | Route / Purpose | Status |
|---|---:|---:|---|---|
| `dist/index.html` | `0.62 kB` | `0.34 kB` | SPA entry document | **PASS** |
| `dist/assets/index-BHcNSwqX.css` | `17.36 kB` | `3.40 kB` | Hand-written clinical design system tokens & layout CSS | **PASS** |
| `dist/assets/index-CURRdl97.js` | `228.76 kB` | `73.66 kB` | Core React 18, React Router, TanStack Query, Auth & AppShell | **PASS** |
| `dist/assets/DashboardPage-z4_IHqXe.js` | `464.27 kB` | `130.01 kB` | Lazy-loaded Recharts chunk + Dashboard view | **PASS** |
| `dist/assets/ReportsPage-BPNDmIgq.js` | `7.65 kB` | `2.57 kB` | Lazy-loaded Verified Reports & Metric Inspector view | **PASS** |
| `dist/assets/AnalysesPage-Dg_YEL9Y.js` | `7.03 kB` | `2.60 kB` | Lazy-loaded CrewAI 6-Agent Live Monitor view | **PASS** |
| `dist/assets/DatasetsPage-DLWzeOwA.js` | `6.44 kB` | `2.34 kB` | Lazy-loaded Dataset Upload & Quality Report view | **PASS** |
| `dist/assets/ChatPage-Ced0mTKg.js` | `5.03 kB` | `2.05 kB` | Lazy-loaded Grounded AI Chat view | **PASS** |
| `dist/assets/ApprovalsPage-XzghIXWc.js` | `5.02 kB` | `1.88 kB` | Lazy-loaded HITL Governance & Approvals view | **PASS** |
| `dist/assets/AdminPage-DZegNlJj.js` | `4.98 kB` | `1.73 kB` | Lazy-loaded Admin Governance Console view | **PASS** |
| `dist/assets/HistoryPage-C7bAkEGn.js` | `3.03 kB` | `1.32 kB` | Lazy-loaded Analysis & Report History view | **PASS** |
| `dist/assets/BusinessProfilePage-Cqhw2eim.js` | `2.87 kB` | `1.19 kB` | Lazy-loaded Business Profile view | **PASS** |
| Self-hosted `@fontsource/inter` `.woff2` (`400/500/600/700` Latin) | `~23.7 kB` each | Pre-compressed `woff2` | Zero external Google Fonts network requests | **PASS** |

---

## 2. Backend Latencies, Database Query Performance (`EXPLAIN`), & Worker Execution Time

### 2.1 Measured API & Service Latencies on `01_Healthcare.xlsx` (`7,100` rows in PostgreSQL `18.7`)

| Endpoint / Operation | Target | Actual Measured Latency | Status |
|---|---|---:|---|
| **FastAPI Startup Time** | `< 2,000 ms` | `~650 ms` | **PASS** |
| **Vite Dev Server Startup Time** | `< 1,000 ms` | `248 ms – 372 ms` | **PASS** |
| `GET /api/v1/health` | `< 50 ms` | `1.7 ms` | **PASS** |
| `GET /docs` (with per-request CSP nonce) | `< 50 ms` | `2.7 ms` | **PASS** |
| `build_kpis` (`/api/v1/datasets/{id}/kpis`, all 9 cards + MoM) | `< 300 ms` | **`252.7 ms`** (`222.3 ms` warm) | **PASS** |
| `build_trends` (`/api/v1/datasets/{id}/trends`, 6-month series + anomalies) | `< 300 ms` | **`222.4 ms`** | **PASS** |
| `build_breakdown` (`/api/v1/datasets/{id}/breakdowns/department`) | `< 300 ms` | **`81.8 ms`** | **PASS** |
| **Worker 6-Agent Pipeline Execution** (`Data Analyst → Marketing → Finance → Operations → Strategy → Verification`) | `< 900,000 ms` (`ANALYSIS_TIMEOUT_SECONDS=900`) | **`426 ms`** total (`131ms + 20ms + 35ms + 39ms + 1ms + 48ms` + DB commit) in deterministic tool-driven mode | **PASS** |

### 2.2 PostgreSQL Query Plans (`EXPLAIN`) & N+1 Query Prevention

Verified directly against PostgreSQL `18.7`:
1. **Appointments by Status (`ix_appointments_dataset_status` Index-Only Scan):**
   ```text
   GroupAggregate  (cost=0.28..76.57 rows=4 width=17)
     Group Key: status
     ->  Index Only Scan using ix_appointments_dataset_status on appointments  (cost=0.28..64.03 rows=2500 width=9)
           Index Cond: (dataset_id = 'e364cdb8-f873-4c08-a936-c15cc1e32492'::uuid)
   ```
2. **Invoices by Month (`ix_invoices_dataset_payment_status` Bitmap Index Scan):**
   ```text
   HashAggregate  (cost=142.73..142.81 rows=6 width=40)
     Group Key: month
     ->  Bitmap Heap Scan on invoices  (cost=26.23..133.73 rows=1800 width=16)
           Recheck Cond: (dataset_id = 'e364cdb8-f873-4c08-a936-c15cc1e32492'::uuid)
           ->  Bitmap Index Scan on ix_invoices_dataset_payment_status  (cost=0.00..25.78 rows=1800 width=0)
   ```
3. **N+1 Query Check:**
   - All 27 metrics in `backend/app/metrics/registry.py` use SQL `GROUP BY` and `SUM/AVG/COUNT` aggregates executed inside PostgreSQL rather than Python row iteration.
   - `list_reports` uses a single SQL `JOIN` (`select(Report, AnalysisRun.dataset_id).join(AnalysisRun, ...)`) rather than per-row queries.

---

## 3. Fault-Tolerance, Error Recovery & Resilience Testing

| Failure Scenario | Expected Behaviour | Actual Tested Behaviour & Evidence | Status |
|---|---|---|---|
| **Database connection fails** | Readiness endpoint returns `503 Service Unavailable` without leaking credentials or stack trace | `test_ready_503_when_database_unreachable`: returns `503` `{"status":"unavailable","database":"unreachable"}` | **PASS** |
| **Worker crashes mid-analysis** | Stuck `RUNNING` analysis is never marked `COMPLETED`; worker startup recovers it as `FAILED` and unlocks the dataset | `test_worker_restart_recovery_and_idempotent_no_duplicate_reports`: `recover_interrupted_runs(db)` transitions `RUNNING` run to `FAILED` with `INTERRUPTED_RUN_MESSAGE` and marks remaining queued steps `SKIPPED` | **PASS** |
| **Duplicate worker execution / Retry idempotency** | Re-executing `execute_analysis_pipeline` on the same `AnalysisRun` updates existing `Report` rather than creating duplicate reports | `test_worker_restart_recovery_and_idempotent_no_duplicate_reports`: `report1.id == report2.id`, `len(all_reports) == 1` | **PASS** |
| **LLM provider fails or exceeds call budget** | `_live_crewai_step_runner` retries up to 3 attempts with exponential backoff (`0.5s`, `1.0s`), enforces `MAX_LLM_CALLS_PER_ANALYSIS=40` (`BudgetExceededError`), and marks run `FAILED` if exhausted | Verified in `test_crewai_definition_context_chaining_and_tool_budget` and `crew.py` lines 126–144 | **PASS** |
| **Upload contains invalid or corrupted rows / files** | Bad rows are quarantined with structured reasons in `quality_report.quarantined_by_reason`; macro/fake/oversized files are rejected with `422` before DB write | `test_quarantine_rules_and_upload_hardening`: 25 injected bad rows quarantined across 11 reason codes while valid rows load cleanly | **PASS** |
| **User refreshes browser during session / analysis** | React `AuthProvider` restores session seamlessly via `/api/v1/auth/refresh` (`httpOnly` cookie), and `AnalysesPage` resumes 2-second polling (`refetchInterval: 2000`) | Verified in live Chrome CDP browser test (`[PASS] Browser page reload preserves session via httpOnly refresh cookie without breaking navigation`) | **PASS** |

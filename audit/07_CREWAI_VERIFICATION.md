# Phase 7 — CrewAI and Multi-Agent Verification

**Project:** MediOps Intelligence — AI-Powered Hospital Operations & Performance Intelligence
**CrewAI Version:** `crewai==1.15.41` (`Process.sequential`)
**Verified Analysis Run ID:** `f5807793-cf1c-4100-8095-238b52f6496f` (and `2c03b4c9-3db0-47d1-b7d7-899208672bbe`)
**Generated Report ID:** `24c65226-b28c-470b-997f-9119138769b3`

---

## 1. Six-Agent Sequential Pipeline & Stored Execution Records

Verified directly against PostgreSQL `analysis_runs` and `agent_executions` (`AnalysisRun.id = f5807793-cf1c-4100-8095-238b52f6496f`, `status = completed`):

| Seq | Agent Slug | Role | Status | Duration (`ms`) | Upstream Context (`context_from`) | Read-Only Tools Invoked (`tool_calls`) | Output Schema | Status |
|---:|---|---|---|---:|---|---|---|---|
| **1** | `data_analyst` | Senior Hospital Data Analyst | `completed` | `131 ms` | `[]` (Initial baseline) | `get_metric(appointments.total)`, `get_metric(appointments.completed)`, `get_metric(appointments.scheduled)`, `get_metric(appointments.avg_wait_minutes)`, `get_anomalies()` | `DomainAgentOutput` (2 findings, 1 data limitation) | **PASS** |
| **2** | `marketing` | Patient Growth & Retention Strategist (Marketing Agent) | `completed` | `20 ms` | `['data_analyst']` | `get_metric(patients.total)`, `get_metric(patients.repeat_visit_count)`, `get_metric(patients.repeat_visit_rate)`, `get_metric(appointments.no_show_rate)`, `get_breakdown(patients.total, insurance_provider)` | `DomainAgentOutput` (2 findings, 1 retention rec, explicit marketing ROI data limitation) | **PASS** |
| **3** | `finance` | Hospital Chief Financial Analyst (Finance Agent) | `completed` | `35 ms` | `['data_analyst']` | `get_metric(finance.net_revenue)`, `get_metric(finance.approved_expenses)`, `get_metric(finance.pending_expenses)`, `get_metric(finance.rejected_expenses)`, `get_metric(finance.approved_margin_pct)`, `get_breakdown(finance.invoice_count, payment_status)` | `DomainAgentOutput` (3 findings, 1 budget rec with `requires_approval=True`) | **PASS** |
| **4** | `operations` | Clinical Operations & Supply Chain Lead (Operations Agent) | `completed` | `39 ms` | `['data_analyst']` | `get_metric(appointments.avg_wait_minutes)`, `get_metric(appointments.wait_over_60_share)`, `get_metric(operations.appointments_per_doctor)`, `get_metric(inventory.low_stock_items)`, `get_metric(inventory.expiring_90d_items)`, `get_metric(inventory.duplicate_batch_count)`, `get_breakdown(appointments.avg_wait_minutes, department)` | `DomainAgentOutput` (3 findings, 2 recs: `purchasing` & `staffing` with `requires_approval=True`) | **PASS** |
| **5** | `strategy` | Chief Hospital Strategy Officer (Strategy Agent) | `completed` | `1 ms` | `['data_analyst', 'marketing', 'finance', 'operations']` | Synthesizes all 4 upstream structured outputs and tool citations | `StrategyReportOutput` (8 sections, 8 consolidated findings, 4 recommendations) | **PASS** |
| **6** | `verification` | Independent Clinical & Financial Auditor (Verification Agent) | `completed` | `48 ms` | `['strategy']` | `get_metric(finance.net_revenue)`, `get_metric(appointments.total)` + Layer-1 `verify_strategy_report` (`33/33` deterministic checks passed) | `VerifierAgentOutput` (`verdict="approved"`, `overall_confidence="high"`) | **PASS** |

---

## 2. Multi-Agent Security, Tool Isolation & Verification Audit

| Requirement | Verification Method & Evidence | Status |
|---|---|---|
| **Agents use read-only metric tools** | All 5 tools in `backend/app/agents/tools.py` (`list_metrics`, `get_metric`, `get_monthly_series`, `get_breakdown`, `get_anomalies`) call read-only functions in `app.metrics.registry`. | **PASS** |
| **Agents cannot execute free-form SQL** | Zero SQL execution tools exist; `dataset_id` is bound server-side inside `ToolExecutionContext` (not controlled by LLM tool arguments), and tool args are validated by strict Pydantic schemas (`_GetMetricArgs`, `_BreakdownArgs`). | **PASS** |
| **Agents receive aggregates rather than raw patient records** | Tools only return aggregate KPI values, monthly series, and dimensional counts/sums. `Patient.patient_name` and `phone_masked` are never returned by any tool. | **PASS** |
| **Agent outputs reference metric keys & deterministic numbers** | Every `FindingItem` carries `metric_keys: list[str]` and `stated_values: dict[str, float]`; every `RecommendationItem` carries `evidence_metric_keys: list[str]`. | **PASS** |
| **Strategy receives required upstream context** | Verified in `create_hospital_tasks` (`strategy_task.context = [data_analyst_task, marketing_task, finance_task, operations_task]`) and in stored `AgentExecution.context_from = ['data_analyst', 'marketing', 'finance', 'operations']`. | **PASS** |
| **Two-Layer Verification checks numeric claims** | Layer 1 (`verifier.py`) checked `33` metric citations and narrative numbers (`33/33 passed`, `0 failed`, `0 unsupported`); Layer 2 (`Verification Agent`) checked contradictions and qualitative data limits (`verdict: "approved"`). | **PASS** |
| **Revision loops work (`Strategy → Verification`)** | Verified in `test_analyses_api_worker_execution_revision_loop_and_cancellation`: corrupting pass-1 `appointments.total = 9999` triggers `Verifier` rejection, increments `revision_count = 1`, re-runs `strategy_rev_1` and `verification_rev_1` (`8` total `AgentExecution` records), and converges to `APPROVED`. | **PASS** |
| **Maximum revision limits are enforced (`MAX_REVISIONS = 2`)** | Verified in `test_rejected_report_creates_zero_pending_recommendations`: when Strategy outputs an unfixable number across passes, the loop terminates at `revision_count == 2`, saves `Report(verdict=Verdict.REJECTED)`, and creates `0` pending recommendations. | **PASS** |
| **Failed LLM calls / worker crashes do not leave jobs stuck** | `_live_crewai_step_runner` retries up to 3 times with exponential backoff and then marks the run `FAILED` with error details; `recover_interrupted_runs` marks any crash-interrupted `RUNNING` run as `FAILED` on worker startup (`test_worker_restart_recovery_and_idempotent_no_duplicate_reports`). | **PASS** |
| **LLM usage limits are enforced (`MAX_LLM_CALLS_PER_ANALYSIS = 40`)** | `ToolExecutionContext.record_call` increments `total_calls` on every tool invocation and raises `BudgetExceededError` (`429 llm_call_budget_exceeded`) when `total_calls > max_calls` (`test_crewai_definition_context_chaining_and_tool_budget`). | **PASS** |
| **No consequential recommendation executes automatically** | Recommendations with `requires_approval=True` (`budget`, `purchasing`, `staffing`, `vendor`) are persisted with `status = pending_approval` and `execution_mode = recorded_decision_only`. | **PASS** |
| **Live External LLM Provider Call (`LLM_API_KEY`)** | Checked `backend/.env` and environment in Phase 1: `LLM_API_KEY` is empty (`False`). Per Phase 7 audit rule (*"If a live LLM key is missing, mark live-agent testing BLOCKED. Do not treat mocked tests as proof of a live LLM workflow"*), deterministic tool-driven CrewAI orchestration is **PASS**, while live external LLM API execution (`pytest -m live_llm`) is marked **BLOCKED** pending a live provider `LLM_API_KEY`. | **BLOCKED** (No `LLM_API_KEY` provided in `.env`) |

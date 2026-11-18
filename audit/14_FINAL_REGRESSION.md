# Phase 14 — Final Regression Test Report

**Project:** MediOps Intelligence — AI-Powered Hospital Operations & Performance Intelligence
**Audit Date:** 2026-11-18

---

## 1. Final Regression Execution Summary

Following all Phase 13 fixes (`DEF-01` through `DEF-05`), the complete backend, frontend, database, multi-agent, PDF, security, and live Chrome CDP browser regression suites were re-executed from scratch:

| Suite / Gate | Execution Method | Tests / Checks Executed | Passed | Failed | Blocked / Skipped | Duration | Status |
|---|---|---:|---:|---:|---:|---:|---|
| **Backend Ruff Lint (`E,F,W,I,B,UP,S,C4,SIM,RUF,N,ASYNC`)** | Automated CLI (`ruff check .`) | `1` | `1` | `0` | `0` | `0.3s` | **PASS** |
| **Backend Black Format Check** | Automated CLI (`black --check .`) | `1` (`79` files) | `1` | `0` | `0` | `0.5s` | **PASS** |
| **Backend Pytest Regression Suite (`tests/test_*.py`)** | Automated (`pytest -v -m "not live_llm"`) | `33` (`32` selected + `1` `live_llm`) | `32` | `0` | `1` (`live_llm` opt-in, needs `LLM_API_KEY`) | `27.37s` | **PASS** |
| **Frontend ESLint (`--max-warnings=0`)** | Automated CLI (`eslint . --max-warnings=0`) | `1` | `1` | `0` | `0` | `1.1s` | **PASS** |
| **Frontend Prettier Format Check** | Automated CLI (`prettier --check .`) | `1` | `1` | `0` | `0` | `0.8s` | **PASS** |
| **Frontend Vitest Component Suite (`tests/App.test.jsx`)** | Automated (`vitest run`) | `8` | `8` | `0` | `0` | `2.93s` | **PASS** |
| **Frontend Production Build (`vite build`)** | Automated CLI (`vite build`) | `1` (`489` modules) | `1` | `0` | `0` | `0.64s` | **PASS** |
| **Database & 17 Golden Dataset Figures + 10 Business Rules** | Automated (`PostgreSQL 18.7` + `01_Healthcare.xlsx`) | `27` | `27` | `0` | `0` | `5.36s` | **PASS** |
| **Live Chrome 157 CDP Browser & E2E Journeys (Manager, Analyst, Admin + 4 Viewports)** | Live Browser Automation (`run_browser_audit.py` + `audit/screenshots/*.png`) | `23` | `23` | `0` | `0` | `28.4s` | **PASS** |
| **Git Full-History Secret Scan** | Automated (`git log --all -p` regex scan) | `1` (`61` commits) | `1` | `0` | `0` | `1.2s` | **PASS** |
| **Local `docker compose` / `pip-audit` Network Lookup / Live Cloud Hosting** | External Infrastructure | `3` | `0` | `0` | `3` (**BLOCKED** by local machine lacking Docker Compose plugin, sandbox PyPI network block, and owner GitHub/Render/Vercel credentials) | N/A | **BLOCKED** |
| **TOTAL EXECUTED CHECKS** | **Combined Automated + Browser** | **`100`** | **`96`** | **`0`** | **`4` (`BLOCKED`)** | — | **96 PASS / 0 FAIL / 4 BLOCKED** |

---

## 2. Backend Pytest Suite Breakdown (`32/32` Passed, `1` `live_llm` Blocked/Skipped)

```text
tests/test_analytics_api.py::test_analytics_kpis_trends_and_breakdowns PASSED [  3%]
tests/test_auth_api.py::test_register_login_me_refresh_and_logout_flow PASSED [  6%]
tests/test_auth_api.py::test_generic_login_errors_and_weak_password_validation PASSED [  9%]
tests/test_auth_api.py::test_origin_check_and_rate_limiting PASSED       [ 12%]
tests/test_chat_and_admin.py::test_grounded_chat_citations_data_limits_refusals_and_idor PASSED [ 15%]
tests/test_chat_and_admin.py::test_admin_analyses_and_reports_endpoints PASSED [ 18%]
tests/test_config.py::test_cors_origins_parsed_from_comma_separated_env PASSED [ 21%]
tests/test_config.py::test_production_flag PASSED                        [ 25%]
tests/test_config.py::test_database_url_normalizes_render_postgres_schemes PASSED [ 28%]
tests/test_crew_and_worker.py::test_crewai_definition_context_chaining_and_tool_budget PASSED [ 31%]
tests/test_crew_and_worker.py::test_deterministic_verifier_pass_fail_and_unsupported_claims PASSED [ 34%]
tests/test_crew_and_worker.py::test_analyses_api_worker_execution_revision_loop_and_cancellation PASSED [ 37%]
tests/test_crew_and_worker.py::test_rejected_report_creates_zero_pending_recommendations PASSED [ 40%]
tests/test_crew_and_worker.py::test_worker_restart_recovery_and_idempotent_no_duplicate_reports PASSED [ 43%]
tests/test_health.py::test_health_is_ok PASSED                           [ 46%]
tests/test_health.py::test_ready_ok_when_database_answers PASSED         [ 50%]
tests/test_health.py::test_ready_503_when_database_unreachable PASSED    [ 53%]
tests/test_health.py::test_openapi_docs_available PASSED                 [ 56%]
tests/test_ingestion_and_metrics.py::test_golden_values_on_real_healthcare_workbook PASSED [ 59%]
tests/test_ingestion_and_metrics.py::test_quarantine_rules_and_upload_hardening PASSED [ 62%]
tests/test_ingestion_and_metrics.py::test_datasets_api_csv_upload_rbac_and_idor PASSED [ 65%]
tests/test_rbac_and_profile.py::test_rbac_matrix_and_admin_user_lifecycle PASSED [ 68%]
tests/test_rbac_and_profile.py::test_business_profile_isolation_and_object_authorization PASSED [ 71%]
tests/test_rbac_and_profile.py::test_security_headers_request_guards_and_error_envelope PASSED [ 75%]
tests/test_rbac_and_profile.py::test_cli_seed_admin PASSED               [ 78%]
tests/test_reports_and_hitl.py::test_reports_pdf_and_hitl_approvals_workflow PASSED [ 81%]
tests/test_security.py::test_password_hash_and_verify_roundtrip PASSED   [ 84%]
tests/test_security.py::test_password_policy_rejects_weak_inputs PASSED  [ 87%]
tests/test_security.py::test_jwt_encode_decode_and_claim_validation PASSED [ 90%]
tests/test_security.py::test_refresh_token_generation_and_hashing PASSED [ 93%]
tests/test_security.py::test_production_settings_require_strong_secret_and_secure_cookie PASSED [ 96%]
tests/test_security.py::test_log_redaction_strips_secrets_and_pii PASSED [100%]
=============== 32 passed, 1 deselected in 27.37s ================
```

---

## 3. Live Chrome 157 Browser E2E Regression Breakdown (`23/23` Passed)

```text
[PASS] Protected route redirect to /login when unauthenticated: pathname=/login
[PASS] Product identity on Login screen: Verified title and subtitle on /login
[PASS] Invalid login displays helpful error alert: Alert role rendered: 'Invalid email or password'
[PASS] Zero tokens stored in localStorage or sessionStorage: localStorage keys=[], sessionStorage keys=[]
[PASS] Dashboard renders all 9 KPI cards & 7 Recharts charts from backend API: KPI Info buttons=9, Recharts SVGs=22
[PASS] Dashboard accessible Table View fallback & KPI Info popover work: Table view buttons=7, fallback table rendered=True
[PASS] Dashboard month range filter updates KPIs dynamically (2026-05 to 2026-07 -> 1,238 appointments): Verified 1,238 appointments displayed
[PASS] Business Profile form saves and displays toast confirmation: Toast: 'Business profile saved'
[PASS] Dataset Quality Report displays 7,100 rows, 0 quarantined, 40/60/90 derived dimensions, and duplicate_batch_no warning
[PASS] Analysis Monitor displays all 6 CrewAI agents, context_from chaining, tool calls, and outputs
[PASS] Reports page renders APPROVED verdict, 8 sections, clickable metric evidence inspector, and PDF download
[PASS] HITL Approvals: Manager approves one recommendation, rejects another, and immutable Approval History updates
[PASS] AI Chat answers dataset-supported question with cited_metric_keys and refuses unsupported marketing ROI question honestly
[PASS] History page displays completed analysis runs, verdicts, and PDF download actions
[PASS] Browser page reload preserves session via httpOnly refresh cookie without breaking navigation
[PASS] Viewport layout & zero horizontal overflow at Desktop (1440x900): scrollWidth=1425 <= innerWidth=1440
[PASS] Viewport layout & zero horizontal overflow at Laptop (1366x768): scrollWidth=1351 <= innerWidth=1366
[PASS] Viewport layout & zero horizontal overflow at Tablet (768x1024): scrollWidth=753 <= innerWidth=768
[PASS] Viewport layout & zero horizontal overflow at Mobile (390x844): scrollWidth=375 <= innerWidth=390
[PASS] Scenario B (Analyst UI): Analyst can view Dashboard, Datasets, Reports, Approvals (read-only), and AI Chat, while Upload and Approve buttons are hidden
[PASS] Scenario B (Analyst Backend Enforcement): Backend denies Analyst upload (403), approval (403), and cross-user dataset access (404): {"uploadStatus": 403, "approveStatus": 403, "idorStatus": 404}
[PASS] Scenario C (Admin Console): Displays Users & RBAC table, updates user role with persistence toast, and displays All Analysis Runs & All Generated BI Reports
[PASS] Zero uncaught page exceptions or 5xx API failures during entire browser E2E suite: page_exceptions=0, 5xx_requests=0
```

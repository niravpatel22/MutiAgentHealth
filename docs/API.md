# API

The interactive OpenAPI documentation is served by the backend at **`/docs`**
(raw spec at `/openapi.json`). This file summarizes conventions; Swagger is authoritative.

## Conventions

- Base path: `/api/v1`
- Errors: `{"error": {"code", "message", "details", "request_id"}}`
- Pagination: `?page=&page_size=` returning `{"items", "total", "page", "page_size"}`
- Auth: `Authorization: Bearer <access_token>` (15-minute JWT kept in memory on the client);
  refresh token is stored in an `httpOnly`, `Secure`, `SameSite=Strict` cookie (`careops_refresh`)
  scoped to `/api/v1/auth`.

## Endpoints available through Phase 1

| Method | Path | Role | Purpose |
|---|---|---|---|
| GET | `/api/v1/health` | Public | Liveness: process is up |
| GET | `/api/v1/ready` | Public | Readiness: database answers `SELECT 1` (503 otherwise) |
| POST | `/api/v1/auth/register` | Public | Register a new `manager` account |
| POST | `/api/v1/auth/login` | Public | Sign in; issues access token + sets refresh cookie |
| POST | `/api/v1/auth/refresh` | Cookie | Rotate refresh token and issue a new access token |
| POST | `/api/v1/auth/logout` | Cookie | Revoke refresh-token family and clear cookie |
| GET | `/api/v1/auth/me` | Any signed-in | Current user profile |
| GET | `/api/v1/business-profile` | Any signed-in | Read own business profile |
| PUT | `/api/v1/business-profile` | Any signed-in | Create or update own business profile |
| GET | `/api/v1/admin/users` | `admin` | Paginated list of users |
| PATCH | `/api/v1/admin/users/{user_id}` | `admin` | Update user role or active flag |
| POST | `/api/v1/datasets` | `manager`, `admin` | Upload `.xlsx` or 5 `.csv` files, validate, clean, and load |
| GET | `/api/v1/datasets` | Any signed-in | Paginated list of own datasets (all for `admin`) |
| GET | `/api/v1/datasets/{id}` | Owner or `admin` | Dataset metadata and quality report |
| GET | `/api/v1/datasets/{id}/quality-report` | Owner or `admin` | Detailed ingestion quality report |
| DELETE | `/api/v1/datasets/{id}` | Owner (`manager`) or `admin` | Delete dataset and cascade domain rows |
| GET | `/api/v1/datasets/{id}/kpis` | Owner or `admin` | 9 dashboard KPI cards + supplementary metrics (`?from=&to=`) |
| GET | `/api/v1/datasets/{id}/trends` | Owner or `admin` | Monthly revenue/expenses, appointment status stacks, and anomalies |
| GET | `/api/v1/datasets/{id}/breakdowns/{dimension}` | Owner or `admin` | Dimensional breakdowns (`department`, `payment_status`, `city`, `insurance_provider`, `age_band`, `category`, `doctor_id`, `service_type`, `approval_status`) |
| POST | `/api/v1/analyses` | `manager`, `admin` | Enqueue a 6-agent CrewAI analysis run (`202 Accepted`; 1 active per dataset) |
| GET | `/api/v1/analyses` | Any signed-in | Paginated list of analysis runs |
| GET | `/api/v1/analyses/{id}` | Owner or `admin` | Run status, revision count, verdict, and per-agent pipeline state |
| GET | `/api/v1/analyses/{id}/agents` | Owner or `admin` | Detailed per-agent execution logs (`context_from`, `tool_calls`, `output`) |
| POST | `/api/v1/analyses/{id}/cancel` | Owner (`manager`) or `admin` | Cancel a queued or running analysis |
| GET | `/api/v1/reports` | Any signed-in | Paginated list of generated BI reports |
| GET | `/api/v1/reports/{id}` | Owner or `admin` | Full report (8 sections, findings, verification appendix, recommendations) |
| GET | `/api/v1/reports/{id}/pdf` | Owner or `admin` | Download reproducible executive PDF report |
| GET | `/api/v1/recommendations` | Any signed-in | Paginated list of HITL recommendations (`?status=&report_id=`) |
| GET | `/api/v1/recommendations/{id}` | Owner or `admin` | Recommendation detail, evidence metrics, and approval history |
| POST | `/api/v1/recommendations/{id}/decision` | `manager`, `admin` | Record an `approved` or `rejected` decision with comment (`analyst` forbidden) |
| POST | `/api/v1/chat/sessions` | Any signed-in | Create a grounded Business Q&A chat session for a dataset |
| GET | `/api/v1/chat/sessions` | Any signed-in | Paginated list of chat sessions |
| POST | `/api/v1/chat/sessions/{id}/messages` | Owner or `admin` | Send a question; returns grounded answer + `cited_metric_keys` |
| GET | `/api/v1/chat/sessions/{id}/messages` | Owner or `admin` | Full session message history with `cited_metric_keys` |
| GET | `/api/v1/admin/analyses` | `admin` | Organization-wide list of all analysis runs |
| GET | `/api/v1/admin/reports` | `admin` | Organization-wide list of all generated BI reports |

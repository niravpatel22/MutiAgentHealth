# Architecture — MediOps Intelligence

**AI-Powered Smart Business Operations & Decision Intelligence System: Healthcare Edition**

![System Architecture](architecture.png)

## 1. High-Level System Architecture

```mermaid
flowchart LR
  U["Browser (React 18 + Vite)"] -->|"HTTPS · JWT + httpOnly Refresh Cookie"| API["FastAPI Backend (/api/v1)"]
  API -->|"SQLAlchemy 2.0 · psycopg 3"| DB[("PostgreSQL 16+")]
  API -->|"Deterministic Queries"| ME["Metrics Engine (metrics/registry.py)"]
  ME --> DB
  W["Job Worker (python -m app.worker)"] -->|"SELECT ... FOR UPDATE SKIP LOCKED"| DB
  W --> CREW["CrewAI Sequential Crew (6 Agents)"]
  CREW -->|"Read-only Dataset-Scoped Tools"| ME
  CREW -->|"Layer 1: Deterministic Verifier"| VER["verifier.py"]
  VER --> ME
  CREW -->|"Aggregates Only (Zero PII)"| LLM["LLM Provider (Gemini / OpenAI / Claude)"]
```

### Separation of Responsibilities

| Layer | Module | Responsibility |
|---|---|---|
| **Presentation** | `frontend/src/` | React 18 + Vite SPA, Recharts visualizations with accessible table fallbacks, in-memory JWT + cookie refresh client |
| **API Gateway & RBAC** | `backend/app/api/v1/` | Versioned REST endpoints, Pydantic v2 contracts, FastAPI dependencies enforcing role and object-level (IDOR) authorization |
| **Business Services** | `backend/app/services/` | Domain orchestration independent of HTTP and CrewAI |
| **Ingestion Pipeline** | `backend/app/ingestion/` | Magic-byte signature checks, macro/formula rejection, cleaning, row quarantine with reasons, dimension derivation, transactional bulk load |
| **Metrics Engine** | `backend/app/metrics/registry.py` | **Single source of truth** for all 27 KPIs, monthly series, dimensional breakdowns, and statistical anomalies |
| **Multi-Agent Layer** | `backend/app/agents/` | Six CrewAI agents, chained sequential tasks, 5 read-only dataset-scoped tools, deterministic verifier (`verifier.py`), and Q&A chat assistant |
| **Background Worker** | `backend/app/worker/` | PostgreSQL-backed `SELECT ... FOR UPDATE SKIP LOCKED` job runner executing analyses asynchronously |
| **PDF Builder** | `backend/app/reports/pdf_builder.py` | Reproducible ReportLab + matplotlib PDF generator from stored report and metrics snapshot data |

---

## 2. Database Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
  USERS ||--o| BUSINESS_PROFILES : "owns"
  USERS ||--o{ REFRESH_TOKENS : "rotates"
  USERS ||--o{ DATASETS : "uploads"
  USERS ||--o{ ANALYSIS_RUNS : "requests"
  USERS ||--o{ APPROVAL_HISTORY : "decides"
  USERS ||--o{ CHAT_SESSIONS : "starts"

  DATASETS ||--o{ PATIENTS : "isolates"
  DATASETS ||--o{ DOCTORS : "derives"
  DATASETS ||--o{ SUPPLIERS : "derives"
  DATASETS ||--o{ VENDORS : "derives"
  DATASETS ||--o{ APPOINTMENTS : "isolates"
  DATASETS ||--o{ INVOICES : "isolates"
  DATASETS ||--o{ MEDICINE_ITEMS : "isolates"
  DATASETS ||--o{ EXPENSES : "isolates"
  DATASETS ||--o{ ANALYSIS_RUNS : "analyzed_by"
  DATASETS ||--o{ CHAT_SESSIONS : "grounds"

  PATIENTS ||--o{ APPOINTMENTS : "books"
  DOCTORS ||--o{ APPOINTMENTS : "attends"
  PATIENTS ||--o{ INVOICES : "billed"
  SUPPLIERS ||--o{ MEDICINE_ITEMS : "supplies"
  VENDORS ||--o{ EXPENSES : "incurs"

  ANALYSIS_RUNS ||--o{ AGENT_EXECUTIONS : "logs"
  ANALYSIS_RUNS ||--o| REPORTS : "produces"
  REPORTS ||--o{ RECOMMENDATIONS : "proposes"
  RECOMMENDATIONS ||--o{ APPROVAL_HISTORY : "tracks"
  CHAT_SESSIONS ||--o{ CHAT_MESSAGES : "contains"
```

---

## 3. Six-Agent CrewAI Sequential Workflow & Context Chaining

```mermaid
flowchart LR
  DA["1. Data Analyst Agent"] -->|"context"| MKT["2. Marketing Agent"]
  DA -->|"context"| FIN["3. Finance Agent"]
  DA -->|"context"| OPS["4. Operations Agent"]
  DA -->|"context"| STR["5. Strategy Agent"]
  MKT -->|"context"| STR
  FIN -->|"context"| STR
  OPS -->|"context"| STR
  STR -->|"consolidated report"| VER["6. Verification Agent + Deterministic Verifier"]
  VER -->|"rejected (max 2 revisions)"| STR
  VER -->|"approved / final verdict"| REP[("Stored Report + HITL Recommendations")]
```

---

## 4. Sequence Diagram: Analysis Run, Verification, & HITL Approval

```mermaid
sequenceDiagram
  autonumber
  actor M as Manager
  participant UI as React Frontend
  participant API as FastAPI (/api/v1)
  participant DB as PostgreSQL 16+
  participant W as Worker Process
  participant C as CrewAI (6 Agents)
  participant V as Deterministic Verifier

  M->>UI: Click "Run New Analysis"
  UI->>API: POST /api/v1/analyses {dataset_id}
  API->>DB: Insert analysis_runs (queued) + 6 agent_executions
  API-->>UI: 202 Accepted {id, status: "queued"}

  loop Poll every 2s while queued/running
    UI->>API: GET /api/v1/analyses/{id}
    API-->>UI: Current agent status, elapsed time, tool logs
  end

  W->>DB: SELECT ... FOR UPDATE SKIP LOCKED
  W->>C: Run Data Analyst -> Marketing -> Finance -> Operations -> Strategy -> Verification
  C->>DB: Read aggregates via read-only tools (list_metrics, get_metric, ...)
  W->>V: verify_strategy_report(db, dataset_id, strategy_output)
  alt Verification fails and revision_count < 2
    W->>C: Re-run Strategy -> Verification with structured feedback
  end
  W->>DB: Persist Report (verdict) + pending_approval Recommendations

  M->>UI: Open Approvals (HITL) page, enter comment, click "Approve"
  UI->>API: POST /api/v1/recommendations/{id}/decision {decision, comment}
  API->>DB: Update status + insert ApprovalHistory (no auto-execution)
  API-->>UI: 200 OK {status: "approved", execution_mode: "recorded_decision_only"}
```

---

## 5. Query Performance & Index Verification (`EXPLAIN`)

Verified against PostgreSQL on the 7,100-row `01_Healthcare.xlsx` dataset:

- `EXPLAIN SELECT count(*) FROM appointments WHERE dataset_id = :d AND month IS NOT NULL`
  → `Index Only Scan using ix_appointments_dataset_month on appointments (cost=0.28..64.03 rows=2500 width=0)`
- Measured end-to-end HTTP response times (target `< 300 ms`):
  - `GET /api/v1/datasets/{id}/kpis`: **222.3 ms**
  - `GET /api/v1/datasets/{id}/trends`: **225.8 ms**
  - `GET /api/v1/datasets/{id}/breakdowns/department`: **84.5 ms**

# Phase 1 — Environment and Startup Verification

**Project:** MediOps Intelligence — AI-Powered Hospital Operations & Performance Intelligence
**Audit Date:** 2026-11-18

---

## 1. Environment & Toolchain Verification

| Component | Expected | Actual Observed | Evidence | Status |
|---|---|---|---|---|
| **Python Version** | `>=3.12,<3.13` (`pyproject.toml`) | `Python 3.12.16` (`backend/.venv/Scripts/python.exe`) | `Backend venv Python: Python 3.12.16` | **PASS** |
| **Python Package Manager** | `uv` with locked `backend/uv.lock` | `uv 0.13.9 (6b2d39dcc 2026-11-17 x86_64-pc-windows-msvc)` | `backend/.venv exists: True` | **PASS** |
| **Node.js Version** | `>=20.19` (`frontend/package.json`) | `v24.22.1` | `Node: v24.22.1` | **PASS** |
| **npm Version & Dependencies** | Locked `frontend/package-lock.json` | `npm 11.19.1`, `frontend/node_modules exists: True` | `npm: 11.19.1` | **PASS** |
| **PostgreSQL Availability** | PostgreSQL `16+` listening on `5432` | `PostgreSQL 18.7 on x86_64-windows, compiled by msvc-19.44.35229, 64-bit` (`Port 5432 listening: True`) | `SELECT version()` over `postgresql+psycopg://` | **PASS** |
| **Git Version & Status** | Git installed, repo initialized on `main` | `git version 2.56.1.windows.1`, branch `main` tracking `origin/main` at `8d37191139dbfac5c12a3da4cedb3ed4db993e42` | `git branch -vv`, `git show-ref` | **PASS** |
| **Docker CLI** | Docker installed | `Docker version 29.9.3, build 5457199` (CLI binary present; `C:\Users\Administrator\.docker\config.json` permission warning inside sandbox) | `docker --version` | **PARTIAL** |
| **Docker Compose** | `docker compose` plugin available | `docker: unknown command: docker compose` (Docker Desktop / Compose plugin not installed on this Windows machine; documented in `docs/DECISIONS.md` D-019) | `docker compose version` | **BLOCKED** (Local machine lacks Docker Compose plugin; native PostgreSQL + Python + Node stack runs directly) |

---

## 2. Environment Variables & Secrets Audit (`backend/.env` vs. `backend/.env.example`)

All 23 environment variables in `backend/.env.example` and `VITE_API_BASE_URL` in `frontend/.env.example` were audited without printing any secret values:

| Variable | Documented in `.env.example` | Present in `backend/.env` | Non-Empty Value Set | Secret / Hardcoding Check |
|---|---|---|---|---|
| `APP_NAME` | Yes | Yes | Yes (`MediOps Intelligence`) | Public config |
| `APP_ENV` | Yes | Yes | Yes (`development`) | Public config |
| `LOG_LEVEL` | Yes | Yes | Yes (`INFO`) | Public config |
| `DATABASE_URL` | Yes | Yes | Yes | Not hardcoded in production; normalized by `_normalize_database_url` |
| `CORS_ORIGINS` | Yes | Yes | Yes (`http://localhost:5173`) | Public config |
| `JWT_SECRET` | Yes | Yes | Yes | `SecretStr("")` default in code; enforced `>= 32 chars` when `APP_ENV=production` |
| `JWT_ISSUER` | Yes | Yes | Yes | Public config |
| `JWT_AUDIENCE` | Yes | Yes | Yes | Public config |
| `ACCESS_TOKEN_TTL_MINUTES` | Yes | Yes | Yes (`15`) | Public config |
| `REFRESH_TOKEN_TTL_DAYS` | Yes | Yes | Yes (`7`) | Public config |
| `COOKIE_SECURE` | Yes | Yes | Yes | Enforced `True` when `APP_ENV=production` |
| `ADMIN_EMAIL` | Yes | Yes | Yes | No default in code (`""`) |
| `ADMIN_PASSWORD` | Yes | Yes | Yes | `SecretStr("")` default in code; never committed |
| `MAX_UPLOAD_MB` | Yes | Default (`10`) | Uses `Settings` default `10` | Safe default |
| `MAX_UPLOAD_ROWS` | Yes | Default (`100000`) | Uses `Settings` default `100000` | Safe default |
| `LLM_MODEL` | Yes | Default (`gemini/gemini-2.5-flash`) | Uses `Settings` default | Provider-agnostic model string |
| `LLM_API_KEY` | Yes | No | `False` (Not set in local `.env`) | `SecretStr("")` default; live LLM calls are opt-in when key is provided |
| `LLM_BASE_URL` | Yes | Default (`""`) | Optional | Safe default |
| `LLM_TEMPERATURE` | Yes | Default (`0.2`) | Uses `Settings` default `0.2` | Safe default |
| `LLM_TIMEOUT_SECONDS` | Yes | Default (`60`) | Uses `Settings` default `60` | Safe default |
| `MAX_LLM_CALLS_PER_ANALYSIS` | Yes | Default (`40`) | Uses `Settings` default `40` | Safe default |
| `ANALYSIS_TIMEOUT_SECONDS` | Yes | Default (`900`) | Uses `Settings` default `900` | Safe default |
| `WORKER_POLL_SECONDS` | Yes | Default (`2.0`) | Uses `Settings` default `2.0` | Safe default |

### Environment Security & `.gitignore` Checks
- **Readable errors on missing/invalid production variables:**
  - `Settings(_env_file=None, app_env='production', jwt_secret='')` → raises `ValidationError: Value error, JWT_SECRET must be set (>= 32 chars) in production` (**PASS**).
  - `Settings(_env_file=None, app_env='production', jwt_secret='a'*32, cookie_secure=False)` → raises `ValidationError: Value error, COOKIE_SECURE must be true in production` (**PASS**).
- **No secrets hardcoded or committed:** Verified `backend/app/core/config.py` has empty `SecretStr("")` defaults for `jwt_secret`, `admin_password`, and `llm_api_key`.
- **Frontend environment variables do not expose backend secrets:** `frontend/.env.example` contains only `VITE_API_BASE_URL=http://localhost:8000/api/v1` (**PASS**).
- **`.gitignore` verification:** Confirmed `backend/.env`, `backend/.venv/`, `frontend/node_modules/`, `frontend/dist/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, and `backend/.coverage` are ignored by Git (**PASS**).

---

## 3. Startup Procedure, Migrations & Health Endpoint Verification

### 3.1 Database Migrations (`alembic upgrade head`)
Executed in `backend/`:
```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
0002_domain_healthcare (head)
```
- **Status:** **PASS**

### 3.2 FastAPI Backend, Background Worker & React Frontend Startup
Started all services against live PostgreSQL `18.7`:
1. **PostgreSQL (`127.0.0.1:5432`)**: Active and accepting connections.
2. **FastAPI (`uvicorn app.main:app --host 127.0.0.1 --port 8000`)**:
   ```text
   INFO:     Started server process [12484]
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
   ```
3. **Background Worker (`python -m app.worker`)**:
   ```json
   {"poll_seconds": 2.0, "recovered_interrupted_runs": 0, "event": "worker_started", "level": "info", "timestamp": "2026-11-18T15:45:37.285912Z"}
   {"claimed_job": null, "event": "worker_poll_cycle_ok", "level": "info", "timestamp": "2026-11-18T15:45:37.299172Z"}
   ```
4. **React Frontend (`vite --host 127.0.0.1 --port 5173`)**:
   ```text
   VITE v8.3.8  ready in 372 ms
   ➜  Local:   http://127.0.0.1:5173/
   ```

### 3.3 Endpoint Probes (`/health`, `/ready`, `/docs`, Frontend, CORS)

| Probe Target | HTTP Status | Actual Response / Headers | Status |
|---|---|---|---|
| `GET http://127.0.0.1:8000/api/v1/health` | `200 OK` | `{"status":"ok"}` (`duration_ms: 1.7`) | **PASS** |
| `GET http://127.0.0.1:8000/api/v1/ready` | `200 OK` | `{"status":"ready","database":"ok"}` | **PASS** |
| `GET http://127.0.0.1:8000/health` (root unprefixed) | `404 Not Found` | Mounted under `/api/v1/health` only; root `/health` and `/ready` aliases not mounted (logged as minor improvement for Phase 13) | **PARTIAL** |
| `GET http://127.0.0.1:8000/docs` | `200 OK` | Serves Swagger UI HTML with per-request CSP nonce: `default-src 'none'; script-src 'nonce-7lUmJSi51VI1A2IHwfgiwg' https://cdn.jsdelivr.net; ...` | **PASS** |
| `GET http://127.0.0.1:5173/` | `200 OK` | Serves Vite React SPA (`<!doctype html> <html lang="en">...`) | **PASS** |
| Frontend → Backend CORS (`Origin: http://localhost:5173`) | `200 OK` | `Access-Control-Allow-Origin: http://localhost:5173`, `Access-Control-Allow-Credentials: true` | **PASS** |

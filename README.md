# CareOps Intelligence

**AI-Powered Smart Business Operations & Decision Intelligence System, Healthcare Edition**:
hospital operations and performance intelligence on `data/01_Healthcare.xlsx`
(May 1 – Oct 31, 2026, INR).

Stack: React 18 + Vite · FastAPI · CrewAI + LLM · PostgreSQL 16 · JWT · Docker · GitHub Actions.

> **Status:** Phase 0 (foundation). Features arrive in gated phases; see the build plan in
> `docs/DECISIONS.md` and the phase reports in the commit history.

## Principles

1. Every number is computed by a deterministic metrics engine, never by the LLM.
2. AI agents receive aggregates only, never raw patient rows or PII.
3. No business action is executed automatically; recommendations need human approval.
4. No secrets in Git (`.env` is ignored, gitleaks runs in pre-commit and CI).
5. Data limits are reported honestly (no invented marketing ROI, collections, or forecasts).

## Quick start

### Option A: Docker (recommended)

```bash
cp backend/.env.example backend/.env      # then fill in secrets
docker compose up --build
```

- API: http://localhost:8000 · Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/api/v1/health · Ready: http://localhost:8000/api/v1/ready

### Option B: Native (no Docker)

Prerequisites: [uv](https://docs.astral.sh/uv/) (installs Python 3.12 for you), Node.js ≥ 20.19,
and a reachable PostgreSQL 16.

```bash
# backend
cd backend
uv python install 3.12
uv sync
cp .env.example .env                       # set DATABASE_URL etc.
uv run uvicorn app.main:app --reload       # http://localhost:8000/docs

# frontend (new terminal)
cd frontend
npm ci
npm run dev                                # http://localhost:5173
```

## Scripts

| Task | Make (Linux/macOS/WSL) | PowerShell (Windows) |
|---|---|---|
| Install deps | `make install` | `./scripts/tasks.ps1 install` |
| Lint + format check | `make lint` | `./scripts/tasks.ps1 lint` |
| Auto-format | `make format` | `./scripts/tasks.ps1 format` |
| Tests | `make test` | `./scripts/tasks.ps1 test` |
| Run API (dev) | `make api` | `./scripts/tasks.ps1 api` |
| Run frontend (dev) | `make web` | `./scripts/tasks.ps1 web` |
| Docker stack | `make up` / `make down` | `docker compose up --build` |

Later phases add `migrate`, `seed-admin`, and `load-sample-dataset`.

## Environment variables

All variables are documented in [`backend/.env.example`](backend/.env.example) and
[`frontend/.env.example`](frontend/.env.example). Secrets have no defaults and must be set in
your local `.env` or the hosting provider's settings.

## Project structure

```
backend/   FastAPI app (api/, core/, db/, schemas/, services/, ingestion/, metrics/,
           agents/, worker/, reports/), tests/, Dockerfile, pyproject.toml, uv.lock
frontend/  React + Vite app (src/, tests/)
data/      01_Healthcare.xlsx (synthetic sample dataset)
docs/      ARCHITECTURE, API, SECURITY, DEPLOYMENT, DECISIONS, DEMO_SCRIPT
.github/   CI workflow
```

## Quality gates

- Pre-commit: ruff, black, prettier, eslint, gitleaks, hygiene hooks.
  Install once from the repo root: `uv run --project backend pre-commit install`.
- CI (every push): lint/format, backend + frontend tests, dependency audit, secret scan, Docker build.

## Data notice

The bundled dataset is synthetic. This build is designed for synthetic or de-identified data only.
Loading real patient data requires compliance review (India DPDP Act and client policy).

## License

Proprietary, all rights reserved (to be confirmed by the client).

# Deployment Guide — MediOps Intelligence

This guide covers one-command local Docker deployment and step-by-step cloud deployment for:
- **Backend (API + Worker):** Render (`render.yaml` Blueprint), Railway, or Fly.io
- **Managed PostgreSQL 16:** Render Postgres, Neon, or Supabase
- **Frontend (React + Vite SPA):** Vercel (`frontend/vercel.json`), Netlify (`frontend/public/_redirects`), or Cloudflare Pages

---

## 1. Local Full-Stack Deployment (`docker compose`)

```bash
cp backend/.env.example backend/.env
# Fill in JWT_SECRET, ADMIN_EMAIL, ADMIN_PASSWORD, and optional LLM_API_KEY in backend/.env
docker compose up --build
```

Services started:
- `db`: PostgreSQL 16 (`localhost:5432`)
- `api`: FastAPI backend (`http://localhost:8000`, Swagger at `http://localhost:8000/docs`) — automatically runs `alembic upgrade head` and seeds the initial admin on startup
- `worker`: CrewAI background job processor (`python -m app.worker`)
- `frontend`: React production build on unprivileged Nginx (`http://localhost:5173`)

---

## 2. Cloud Deployment: Backend & Managed PostgreSQL

### Option A: Render Blueprint (Recommended, 1-Click via `render.yaml`)

1. Push the repository to GitHub (`https://github.com/niravpatel22/MutiAgentHealth`).
2. In the Render Dashboard, open **Blueprints → New Blueprint Instance** and connect `niravpatel22/MutiAgentHealth`.
3. Render reads [`render.yaml`](../render.yaml) and provisions:
   - `careops-db`: Managed PostgreSQL database (`healthcare_bi`)
   - `careops-api`: Docker web service built from `./backend/Dockerfile` with health check `/api/v1/health`
   - `careops-worker`: Docker worker service running `python -m app.worker`
4. Enter the prompted secret environment variables (`ADMIN_EMAIL`, `ADMIN_PASSWORD`, `LLM_API_KEY`) and click **Apply**.
5. Once your frontend is deployed (Section 3), update `CORS_ORIGINS` on `careops-api` to your live frontend URL (e.g. `https://careops-intelligence.vercel.app`).

### Option B: Railway or Fly.io (Docker)

- Point both the **API service** and the **Worker service** at `backend/Dockerfile` (build context `./backend`).
- API start command (default in `Dockerfile`):
  ```bash
  sh -c "alembic upgrade head && ([ -z \"$ADMIN_EMAIL\" ] || python -m app.cli seed-admin) && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"
  ```
- Worker start command:
  ```bash
  python -m app.worker
  ```
- Connect a managed PostgreSQL 16 instance from **Neon** (`https://neon.tech`) or **Supabase** (`https://supabase.com`) and set `DATABASE_URL` (our config automatically normalizes `postgres://` and `postgresql://` into `postgresql+psycopg://`).

---

## 3. Cloud Deployment: Frontend (Netlify / Vercel / Cloudflare Pages)

### Option A: One-Click Netlify Deploy (Pre-Wired to Render API via `netlify.toml`)

1. Click or open: **https://app.netlify.com/start/deploy?repository=https://github.com/niravpatel22/MutiAgentHealth**
2. Netlify reads [`netlify.toml`](../netlify.toml) automatically:
   - **Base directory:** `frontend`
   - **Build command:** `npm ci && npm run build`
   - **Publish directory:** `dist`
   - **API Edge Proxy (`/api/v1/*`):** Automatically proxies `/api/v1/*` to `https://careops-api.onrender.com/api/v1/:splat` (`200`), so first-party `SameSite=Strict` `httpOnly` `Secure` refresh cookies and all FastAPI endpoints work seamlessly with zero CORS preflight issues.
   - **Pre-Seeded Demo Login Buttons:** The Login screen includes one-click **Fill Manager**, **Fill Admin**, and **Fill Analyst** buttons pre-seeded on the Render backend (`python -m app.cli seed-demo`).

### Option B: Vercel or Cloudflare Pages

1. Import the GitHub repository into **Vercel** or **Cloudflare Pages**.
2. Set the project settings:
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build`
   - **Output Directory:** `dist`
3. Set the environment variable:
   - `VITE_API_BASE_URL=https://careops-api.onrender.com/api/v1`
4. SPA deep-link routing and security headers are pre-configured in [`frontend/vercel.json`](../frontend/vercel.json) and [`frontend/public/_redirects`](../frontend/public/_redirects).

---

## 4. Environment Variables Reference

### Backend (`backend/.env`)

| Variable | Required in Prod | Default | Description |
|---|---|---|---|
| `APP_ENV` | Yes | `development` | Set to `production` in cloud deployments |
| `DATABASE_URL` | Yes | local Postgres | PostgreSQL connection URL (auto-normalized to `postgresql+psycopg://`) |
| `CORS_ORIGINS` | Yes | `http://localhost:5173` | Comma-separated list of allowed frontend origins |
| `JWT_SECRET` | Yes (>=32 chars) | — | Secret key for signing 15-min HS256 access tokens |
| `COOKIE_SECURE` | Yes (`true`) | `true` | Enforces HTTPS-only refresh cookie |
| `ADMIN_EMAIL` | Yes | — | Email for initial seeded `admin` user |
| `ADMIN_PASSWORD` | Yes (12+ chars) | — | Password for initial seeded `admin` user |
| `LLM_MODEL` | Yes | `gemini/gemini-2.5-flash` | Provider/model identifier (`gemini/...`, `openai/...`, `anthropic/...`) |
| `LLM_API_KEY` | For live LLM | — | API key for the chosen LLM provider (server-only, never in frontend) |
| `LLM_TEMPERATURE` | No | `0.2` | Sampling temperature |
| `MAX_LLM_CALLS_PER_ANALYSIS` | No | `40` | Hard per-analysis tool/LLM call budget |
| `ANALYSIS_TIMEOUT_SECONDS` | No | `900` | Hard per-analysis timeout (15 minutes) |

### Frontend (`frontend/.env`)

| Variable | Required | Example | Description |
|---|---|---|---|
| `VITE_API_BASE_URL` | Yes | `https://careops-api.onrender.com/api/v1` | Public URL of the FastAPI `/api/v1` prefix |

---

## 5. Post-Deploy Verification Checklist

- [ ] `GET https://<backend-url>/api/v1/health` returns `{"status": "ok"}`.
- [ ] `GET https://<backend-url>/api/v1/ready` returns `{"status": "ready", "database": "ok"}`.
- [ ] `GET https://<backend-url>/docs` loads Swagger UI with nonce-protected CSP.
- [ ] Sign in on the live frontend URL with `ADMIN_EMAIL` / `ADMIN_PASSWORD`.
- [ ] Upload `data/01_Healthcare.xlsx` and confirm `7,100` rows load with `0` quarantined and the `duplicate_batch_no` warning (`6` duplicate batches across `12` items).
- [ ] Run a 6-agent analysis, verify the report verdict is `APPROVED`, download the PDF report, and record one Human-in-the-Loop approval decision.

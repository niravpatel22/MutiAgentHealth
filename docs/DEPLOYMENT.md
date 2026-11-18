# Deployment

> Stub (Phase 0). Full step-by-step guides (Vercel/Netlify/Cloudflare Pages, Render/Railway/Fly.io,
> Neon/Supabase), `render.yaml`, frontend host config, and the post-deploy checklist land in Phase 7.

## Shape of the deployment

| Component | Artifact | Start command |
|---|---|---|
| API | `backend/Dockerfile` image | `uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers` |
| Worker (Phase 4) | same image | `python -m app.worker` |
| Frontend | `frontend/dist` static build | served by the static host |
| Database | managed PostgreSQL 16 | n/a |

All configuration is through environment variables listed in `backend/.env.example` and
`frontend/.env.example`. Secrets are set only in the host's environment settings.

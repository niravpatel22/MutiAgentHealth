# API

The interactive OpenAPI documentation is served by the backend at **`/docs`**
(raw spec at `/openapi.json`). This file summarizes conventions; Swagger is authoritative.

## Conventions

- Base path: `/api/v1`
- Errors (from Phase 1): `{"error": {"code", "message", "details", "request_id"}}`
- Pagination (from Phase 1): `?page=&page_size=` with `{items, total, page, page_size}`

## Endpoints available now

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Liveness: process is up |
| GET | `/api/v1/ready` | Readiness: database answers `SELECT 1` (503 otherwise) |

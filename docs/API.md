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

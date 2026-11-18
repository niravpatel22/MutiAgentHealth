"""Liveness and readiness probes."""

from typing import Literal

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.logging import get_logger
from app.db import session as db_session

router = APIRouter(tags=["ops"])
log = get_logger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ready", "unavailable"]
    database: Literal["ok", "unreachable"]


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Returns 200 while the process is running. Does not touch the database.",
)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=ReadyResponse,
    summary="Readiness probe",
    description="Returns 200 when the database answers `SELECT 1`, otherwise 503.",
    responses={503: {"model": ReadyResponse, "description": "Database unreachable"}},
)
def ready(response: Response) -> ReadyResponse:
    try:
        db_session.ping_database()
    except Exception as exc:  # any driver/network error means "not ready"
        log.warning("readiness_check_failed", error_type=type(exc).__name__)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadyResponse(status="unavailable", database="unreachable")
    return ReadyResponse(status="ready", database="ok")

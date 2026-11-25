"""Analyses router: enqueue runs (202 Accepted), poll status & agent logs, and cancel."""

import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status

from app.api.deps import AppSettings, CurrentUser, DbSession, ManagerOrAdmin
from app.core.rate_limit import AUTH_LIMIT, limiter
from app.db.session import get_sessionmaker
from app.schemas.analysis import (
    AgentExecutionOut,
    AnalysisCreateRequest,
    AnalysisDetailOut,
    AnalysisRunOut,
)
from app.schemas.common import Page, PageParams, error_responses
from app.services import analysis_service

router = APIRouter(prefix="/analyses", tags=["analyses"])


def _kick_inline_worker_if_single_process(run_in_background: bool) -> None:
    if not run_in_background:
        return
    from app.worker.runner import process_next_analysis_job

    with get_sessionmaker()() as db:
        process_next_analysis_job(db)


@router.post(
    "",
    response_model=AnalysisDetailOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue a 6-agent CrewAI analysis run on a dataset",
    description=(
        "Enqueues an analysis job in the PostgreSQL queue (`SELECT ... FOR UPDATE SKIP LOCKED`) "
        "and returns `202 Accepted` immediately with the analysis ID and initial queued agent "
        "steps. Enforces one active analysis per dataset (`409 Conflict`)."
    ),
    responses=error_responses(401, 403, 404, 409, 422, 429),
)
@limiter.limit(AUTH_LIMIT)
def create_analysis(
    request: Request,
    body: AnalysisCreateRequest,
    background_tasks: BackgroundTasks,
    user: ManagerOrAdmin,
    db: DbSession,
    settings: AppSettings,
    run_inline: Annotated[
        bool,
        Query(description="When true, triggers a worker tick in background after returning 202."),
    ] = True,
) -> AnalysisDetailOut:
    run = analysis_service.enqueue_analysis(db, user, body.dataset_id)
    if run_inline and settings.app_env != "test":
        background_tasks.add_task(_kick_inline_worker_if_single_process, True)
    return analysis_service.get_analysis_detail(db, user, run.id)


@router.get(
    "",
    response_model=Page[AnalysisRunOut],
    summary="List analysis runs",
    responses=error_responses(401),
)
def list_analyses(
    user: CurrentUser,
    db: DbSession,
    page: Annotated[PageParams, Depends()],
    dataset_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[AnalysisRunOut]:
    items, total = analysis_service.list_analyses(db, user, page, dataset_id=dataset_id)
    return Page[AnalysisRunOut](
        items=[AnalysisRunOut.model_validate(r) for r in items],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get(
    "/{analysis_id}",
    response_model=AnalysisDetailOut,
    summary="Get analysis run status, revision count, and per-agent pipeline state",
    responses=error_responses(401, 404),
)
def get_analysis(analysis_id: uuid.UUID, user: CurrentUser, db: DbSession) -> AnalysisDetailOut:
    return analysis_service.get_analysis_detail(db, user, analysis_id)


@router.get(
    "/{analysis_id}/agents",
    response_model=list[AgentExecutionOut],
    summary="Get detailed per-agent execution logs and tool calls",
    responses=error_responses(401, 404),
)
def get_analysis_agents(
    analysis_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[AgentExecutionOut]:
    agents = analysis_service.get_analysis_agents(db, user, analysis_id)
    return [AgentExecutionOut.model_validate(a) for a in agents]


@router.post(
    "/{analysis_id}/cancel",
    response_model=AnalysisRunOut,
    summary="Cancel a queued or running analysis",
    responses=error_responses(400, 401, 403, 404),
)
def cancel_analysis(analysis_id: uuid.UUID, user: ManagerOrAdmin, db: DbSession) -> AnalysisRunOut:
    run = analysis_service.cancel_analysis(db, user, analysis_id)
    return AnalysisRunOut.model_validate(run)

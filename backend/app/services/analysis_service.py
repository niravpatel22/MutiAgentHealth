"""Analysis orchestration service: enqueueing, status polling, agent logs, and cancellation."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import ensure_owner_or_admin
from app.core.errors import AppError, ConflictError, NotFoundError
from app.db.base import utcnow
from app.db.models import (
    AgentExecution,
    AgentStatus,
    AnalysisRun,
    AnalysisStatus,
    Report,
    Role,
    User,
)
from app.schemas.analysis import AGENT_PIPELINE, AgentExecutionOut, AnalysisDetailOut
from app.schemas.common import PageParams
from app.services import dataset_service

ACTIVE_STATUSES = (AnalysisStatus.QUEUED, AnalysisStatus.RUNNING)


def enqueue_analysis(db: Session, user: User, dataset_id: uuid.UUID) -> AnalysisRun:
    dataset = dataset_service.get_dataset_for_user(db, user, dataset_id)
    active = db.scalar(
        select(AnalysisRun).where(
            AnalysisRun.dataset_id == dataset.id,
            AnalysisRun.status.in_(ACTIVE_STATUSES),
        )
    )
    if active is not None:
        raise ConflictError(
            "An analysis is already queued or running for this dataset",
            details={"active_analysis_id": str(active.id), "status": active.status.value},
        )

    run = AnalysisRun(
        dataset_id=dataset.id,
        requested_by=user.id,
        status=AnalysisStatus.QUEUED,
        revision_count=0,
    )
    db.add(run)
    db.flush()

    for meta in AGENT_PIPELINE:
        db.add(
            AgentExecution(
                analysis_id=run.id,
                agent_name=meta.slug,
                sequence=meta.sequence,
                status=AgentStatus.QUEUED,
                context_from=list(meta.context_from),
                tool_calls=[],
                llm_calls=0,
            )
        )
    db.commit()
    db.refresh(run)
    return run


def list_analyses(
    db: Session,
    user: User,
    page: PageParams,
    *,
    dataset_id: uuid.UUID | None = None,
) -> tuple[list[AnalysisRun], int]:
    base = select(AnalysisRun)
    cnt = select(func.count()).select_from(AnalysisRun)
    if user.role != Role.ADMIN:
        base = base.where(AnalysisRun.requested_by == user.id)
        cnt = cnt.where(AnalysisRun.requested_by == user.id)
    if dataset_id is not None:
        base = base.where(AnalysisRun.dataset_id == dataset_id)
        cnt = cnt.where(AnalysisRun.dataset_id == dataset_id)
    total = int(db.scalar(cnt) or 0)
    items = list(
        db.scalars(
            base.order_by(AnalysisRun.created_at.desc()).offset(page.offset).limit(page.page_size)
        ).all()
    )
    return items, total


def get_analysis_for_user(db: Session, user: User, analysis_id: uuid.UUID) -> AnalysisRun:
    run = db.get(AnalysisRun, analysis_id)
    if run is None:
        raise NotFoundError("Analysis run not found")
    ensure_owner_or_admin(user, run.requested_by, "Analysis run")
    return run


def get_analysis_agents(db: Session, user: User, analysis_id: uuid.UUID) -> list[AgentExecution]:
    run = get_analysis_for_user(db, user, analysis_id)
    return list(
        db.scalars(
            select(AgentExecution)
            .where(AgentExecution.analysis_id == run.id)
            .order_by(AgentExecution.sequence)
        ).all()
    )


def get_analysis_detail(db: Session, user: User, analysis_id: uuid.UUID) -> AnalysisDetailOut:
    run = get_analysis_for_user(db, user, analysis_id)
    agents = list(
        db.scalars(
            select(AgentExecution)
            .where(AgentExecution.analysis_id == run.id)
            .order_by(AgentExecution.sequence)
        ).all()
    )
    report = db.scalar(select(Report).where(Report.analysis_id == run.id))
    return AnalysisDetailOut(
        id=run.id,
        dataset_id=run.dataset_id,
        requested_by=run.requested_by,
        status=run.status,
        current_agent=run.current_agent,
        revision_count=run.revision_count,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error=run.error,
        created_at=run.created_at,
        agents=[AgentExecutionOut.model_validate(a) for a in agents],
        report_id=report.id if report else None,
        verdict=report.verdict.value if report else None,
    )


def cancel_analysis(db: Session, user: User, analysis_id: uuid.UUID) -> AnalysisRun:
    run = get_analysis_for_user(db, user, analysis_id)
    if run.status not in ACTIVE_STATUSES:
        raise AppError(
            f"Cannot cancel an analysis with status '{run.status.value}'",
            code="invalid_analysis_state",
        )
    run.status = AnalysisStatus.CANCELLED
    run.current_agent = None
    run.finished_at = utcnow()
    for ex in db.scalars(
        select(AgentExecution).where(
            AgentExecution.analysis_id == run.id,
            AgentExecution.status.in_((AgentStatus.QUEUED, AgentStatus.RUNNING)),
        )
    ).all():
        ex.status = AgentStatus.SKIPPED
        ex.finished_at = utcnow()
    db.commit()
    db.refresh(run)
    return run

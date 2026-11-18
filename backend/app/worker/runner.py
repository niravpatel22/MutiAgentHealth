"""PostgreSQL-backed job queue runner (`SELECT ... FOR UPDATE SKIP LOCKED`)."""

import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.crew import AnalysisCancelledError, StepRunner, execute_analysis_pipeline
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.base import utcnow
from app.db.models import AnalysisRun, AnalysisStatus, BusinessProfile
from app.db.session import get_sessionmaker

log = get_logger(__name__)


def claim_next_queued_run(db: Session) -> AnalysisRun | None:
    """Atomically claim the oldest queued AnalysisRun using FOR UPDATE SKIP LOCKED."""
    stmt = (
        select(AnalysisRun)
        .where(AnalysisRun.status == AnalysisStatus.QUEUED)
        .order_by(AnalysisRun.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    run = db.scalar(stmt)
    if run is None:
        return None
    run.status = AnalysisStatus.RUNNING
    run.started_at = utcnow()
    db.commit()
    db.refresh(run)
    return run


def process_next_analysis_job(
    db: Session,
    settings: Settings | None = None,
    *,
    step_runner: StepRunner | None = None,
) -> AnalysisRun | None:
    """Claim and run a single queued analysis job if one exists. Returns the processed run."""
    settings = settings or get_settings()
    run = claim_next_queued_run(db)
    if run is None:
        return None

    profile = db.scalar(select(BusinessProfile).where(BusinessProfile.user_id == run.requested_by))
    b_ctx = ""
    if profile is not None:
        b_ctx = (
            f"Company: {profile.company_name} | Industry: {profile.industry} | "
            f"Team size: {profile.team_size} | Goals: {profile.business_goals}"
        )

    log.info("analysis_job_started", analysis_id=str(run.id), dataset_id=str(run.dataset_id))
    try:
        execute_analysis_pipeline(
            db, settings, run, business_context=b_ctx, step_runner=step_runner
        )
        log.info(
            "analysis_job_completed",
            analysis_id=str(run.id),
            revisions=run.revision_count,
        )
    except AnalysisCancelledError:
        db.refresh(run)
        run.status = AnalysisStatus.CANCELLED
        run.current_agent = None
        run.finished_at = utcnow()
        db.commit()
        log.info("analysis_job_cancelled", analysis_id=str(run.id))
    except Exception as exc:
        db.refresh(run)
        run.status = AnalysisStatus.FAILED
        run.current_agent = None
        run.finished_at = utcnow()
        run.error = f"{type(exc).__name__}: {exc}"
        db.commit()
        log.error(
            "analysis_job_failed",
            analysis_id=str(run.id),
            error_type=type(exc).__name__,
            error_msg=str(exc),
        )
    db.refresh(run)
    return run


def run_worker_forever(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    session_factory = get_sessionmaker()
    log.info("worker_started", poll_seconds=settings.worker_poll_seconds)

    while True:
        with session_factory() as db:
            processed = process_next_analysis_job(db, settings)
        if processed is None:
            time.sleep(settings.worker_poll_seconds)

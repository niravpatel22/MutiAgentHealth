"""Reports and Human-in-the-Loop (HITL) recommendation services."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import ensure_owner_or_admin
from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import (
    AnalysisRun,
    ApprovalHistory,
    Dataset,
    Decision,
    Recommendation,
    RecommendationStatus,
    Report,
    Role,
    User,
)
from app.reports.pdf_builder import build_report_pdf
from app.schemas.common import PageParams
from app.schemas.report import (
    ApprovalHistoryOut,
    RecommendationDecisionRequest,
    RecommendationOut,
    ReportDetailOut,
    ReportOut,
)

log = get_logger(__name__)


def _get_report_and_run(
    db: Session, user: User, report_id: uuid.UUID
) -> tuple[Report, AnalysisRun]:
    report = db.get(Report, report_id)
    if report is None:
        raise NotFoundError("Report not found")
    run = db.get(AnalysisRun, report.analysis_id)
    if run is None:
        raise NotFoundError("Report not found")
    ensure_owner_or_admin(user, run.requested_by, "Report")
    return report, run


def _hydrate_recommendation(db: Session, rec: Recommendation, snapshot: dict) -> RecommendationOut:
    history = list(
        db.scalars(
            select(ApprovalHistory)
            .where(ApprovalHistory.recommendation_id == rec.id)
            .order_by(ApprovalHistory.decided_at.desc())
        ).all()
    )
    evidence_metrics = [
        snapshot[k]
        for k in rec.evidence_metric_keys
        if isinstance(snapshot, dict) and k in snapshot
    ]
    return RecommendationOut(
        id=rec.id,
        report_id=rec.report_id,
        title=rec.title,
        rationale=rec.rationale,
        action_type=rec.action_type,
        evidence_metric_keys=rec.evidence_metric_keys,
        status=rec.status,
        created_at=rec.created_at,
        evidence_metrics=evidence_metrics,
        approval_history=[ApprovalHistoryOut.model_validate(h) for h in history],
    )


def list_reports(
    db: Session,
    user: User,
    page: PageParams,
    *,
    dataset_id: uuid.UUID | None = None,
) -> tuple[list[ReportOut], int]:
    stmt = select(Report, AnalysisRun.dataset_id).join(
        AnalysisRun, AnalysisRun.id == Report.analysis_id
    )
    cnt_stmt = (
        select(func.count())
        .select_from(Report)
        .join(AnalysisRun, AnalysisRun.id == Report.analysis_id)
    )
    if user.role != Role.ADMIN:
        stmt = stmt.where(AnalysisRun.requested_by == user.id)
        cnt_stmt = cnt_stmt.where(AnalysisRun.requested_by == user.id)
    if dataset_id is not None:
        stmt = stmt.where(AnalysisRun.dataset_id == dataset_id)
        cnt_stmt = cnt_stmt.where(AnalysisRun.dataset_id == dataset_id)

    total = int(db.scalar(cnt_stmt) or 0)
    rows = db.execute(
        stmt.order_by(Report.created_at.desc()).offset(page.offset).limit(page.page_size)
    ).all()
    items = [
        ReportOut(
            id=rep.id,
            analysis_id=rep.analysis_id,
            dataset_id=ds_id,
            verdict=rep.verdict,
            confidence=rep.confidence,
            created_at=rep.created_at,
        )
        for rep, ds_id in rows
    ]
    return items, total


def get_report_detail(db: Session, user: User, report_id: uuid.UUID) -> ReportDetailOut:
    report, run = _get_report_and_run(db, user, report_id)
    recs = list(
        db.scalars(
            select(Recommendation)
            .where(Recommendation.report_id == report.id)
            .order_by(Recommendation.created_at.asc())
        ).all()
    )
    return ReportDetailOut(
        id=report.id,
        analysis_id=report.analysis_id,
        dataset_id=run.dataset_id,
        verdict=report.verdict,
        confidence=report.confidence,
        created_at=report.created_at,
        content=report.content,
        metrics_snapshot=report.metrics_snapshot,
        verification=report.verification,
        recommendations=[_hydrate_recommendation(db, r, report.metrics_snapshot) for r in recs],
    )


def render_report_pdf(db: Session, user: User, report_id: uuid.UUID) -> bytes:
    report, run = _get_report_and_run(db, user, report_id)
    dataset = db.get(Dataset, run.dataset_id)
    recs = list(
        db.scalars(
            select(Recommendation)
            .where(Recommendation.report_id == report.id)
            .order_by(Recommendation.created_at.asc())
        ).all()
    )
    ds_name = dataset.name if dataset else "Hospital Operations Dataset"
    return build_report_pdf(report, recs, dataset_name=ds_name)


def list_recommendations(
    db: Session,
    user: User,
    page: PageParams,
    *,
    status_filter: RecommendationStatus | None = None,
    report_id: uuid.UUID | None = None,
) -> tuple[list[RecommendationOut], int]:
    stmt = (
        select(Recommendation, Report)
        .join(Report, Report.id == Recommendation.report_id)
        .join(AnalysisRun, AnalysisRun.id == Report.analysis_id)
    )
    cnt_stmt = (
        select(func.count())
        .select_from(Recommendation)
        .join(Report, Report.id == Recommendation.report_id)
        .join(AnalysisRun, AnalysisRun.id == Report.analysis_id)
    )
    if user.role != Role.ADMIN:
        stmt = stmt.where(AnalysisRun.requested_by == user.id)
        cnt_stmt = cnt_stmt.where(AnalysisRun.requested_by == user.id)
    if status_filter is not None:
        stmt = stmt.where(Recommendation.status == status_filter)
        cnt_stmt = cnt_stmt.where(Recommendation.status == status_filter)
    if report_id is not None:
        stmt = stmt.where(Recommendation.report_id == report_id)
        cnt_stmt = cnt_stmt.where(Recommendation.report_id == report_id)

    total = int(db.scalar(cnt_stmt) or 0)
    rows = db.execute(
        stmt.order_by(Recommendation.created_at.desc()).offset(page.offset).limit(page.page_size)
    ).all()
    items = [_hydrate_recommendation(db, rec, rep.metrics_snapshot) for rec, rep in rows]
    return items, total


def get_recommendation_detail(
    db: Session, user: User, recommendation_id: uuid.UUID
) -> RecommendationOut:
    rec = db.get(Recommendation, recommendation_id)
    if rec is None:
        raise NotFoundError("Recommendation not found")
    report, _ = _get_report_and_run(db, user, rec.report_id)
    return _hydrate_recommendation(db, rec, report.metrics_snapshot)


def decide_recommendation(
    db: Session,
    user: User,
    recommendation_id: uuid.UUID,
    data: RecommendationDecisionRequest,
) -> RecommendationOut:
    """Record a manager/admin decision on a recommendation.

    Never executes any external business action automatically; 'approved' is a recorded governance
    decision stored in ``approval_history``.
    """
    rec = db.get(Recommendation, recommendation_id)
    if rec is None:
        raise NotFoundError("Recommendation not found")
    report, _ = _get_report_and_run(db, user, rec.report_id)

    rec.status = (
        RecommendationStatus.APPROVED
        if data.decision == Decision.APPROVED
        else RecommendationStatus.REJECTED
    )
    history = ApprovalHistory(
        recommendation_id=rec.id,
        decided_by=user.id,
        decision=data.decision,
        comment=data.comment,
        decided_at=utcnow(),
    )
    db.add(history)
    db.commit()
    db.refresh(rec)
    log.info(
        "recommendation_decided",
        recommendation_id=str(rec.id),
        decided_by=str(user.id),
        decision=data.decision.value,
    )
    return _hydrate_recommendation(db, rec, report.metrics_snapshot)

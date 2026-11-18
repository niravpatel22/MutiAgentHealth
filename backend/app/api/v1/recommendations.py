"""Human-in-the-Loop (HITL) recommendations router: list, detail, and manager/admin decisions."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import CurrentUser, DbSession, ManagerOrAdmin
from app.db.models import RecommendationStatus
from app.schemas.common import Page, PageParams, error_responses
from app.schemas.report import RecommendationDecisionRequest, RecommendationOut
from app.services import report_service

router = APIRouter(prefix="/recommendations", tags=["recommendations (HITL)"])


@router.get(
    "",
    response_model=Page[RecommendationOut],
    summary="List recommendations with optional status filter",
    responses=error_responses(401, 422),
)
def list_recommendations(
    user: CurrentUser,
    db: DbSession,
    page: Annotated[PageParams, Depends()],
    status: Annotated[RecommendationStatus | None, Query()] = None,
    report_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[RecommendationOut]:
    items, total = report_service.list_recommendations(
        db, user, page, status_filter=status, report_id=report_id
    )
    return Page[RecommendationOut](
        items=items,
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get(
    "/{recommendation_id}",
    response_model=RecommendationOut,
    summary="Get recommendation detail, evidence metrics, and approval history",
    responses=error_responses(401, 404),
)
def get_recommendation(
    recommendation_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> RecommendationOut:
    return report_service.get_recommendation_detail(db, user, recommendation_id)


@router.post(
    "/{recommendation_id}/decision",
    response_model=RecommendationOut,
    summary="Approve or reject a recommendation (manager or admin only)",
    description=(
        "Records a Human-in-the-Loop governance decision (`approved` or `rejected`) and comment "
        "in `approval_history`. Analysts are forbidden (`403`). The system never executes "
        "business actions automatically (`execution_mode: recorded_decision_only`)."
    ),
    responses=error_responses(401, 403, 404, 422),
)
def decide_recommendation(
    recommendation_id: uuid.UUID,
    body: RecommendationDecisionRequest,
    user: ManagerOrAdmin,
    db: DbSession,
) -> RecommendationOut:
    return report_service.decide_recommendation(db, user, recommendation_id, body)

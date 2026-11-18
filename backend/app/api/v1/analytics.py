"""Dashboard analytics router: KPIs, monthly trends, and dimensional breakdowns."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.analytics import BreakdownResponse, KpisResponse, TrendsResponse
from app.schemas.common import error_responses
from app.services import analytics_service, dataset_service

router = APIRouter(prefix="/datasets/{dataset_id}", tags=["analytics"])

FromMonth = Annotated[
    str | None,
    Query(alias="from", description="Start month (YYYY-MM), e.g. 2026-05", examples=["2026-05"]),
]
ToMonth = Annotated[
    str | None,
    Query(alias="to", description="End month (YYYY-MM), e.g. 2026-10", examples=["2026-10"]),
]


@router.get(
    "/kpis",
    response_model=KpisResponse,
    summary="Get dashboard KPI cards and supplementary metrics",
    description=(
        "Computes all dashboard KPI cards deterministically from the metrics registry, "
        "including month-over-month change, metric definition, and basis."
    ),
    responses=error_responses(400, 401, 404),
)
def get_kpis(
    dataset_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    from_month: FromMonth = None,
    to_month: ToMonth = None,
) -> KpisResponse:
    dataset = dataset_service.get_dataset_for_user(db, user, dataset_id)
    return analytics_service.build_kpis(db, dataset.id, from_month=from_month, to_month=to_month)


@router.get(
    "/trends",
    response_model=TrendsResponse,
    summary="Get monthly trends and statistical anomalies",
    description=(
        "Returns monthly revenue vs expenses (split by Approved, Pending, Rejected), "
        "monthly appointments stacked by status, and flagged month-over-month anomalies."
    ),
    responses=error_responses(400, 401, 404),
)
def get_trends(
    dataset_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    from_month: FromMonth = None,
    to_month: ToMonth = None,
) -> TrendsResponse:
    dataset = dataset_service.get_dataset_for_user(db, user, dataset_id)
    return analytics_service.build_trends(db, dataset.id, from_month=from_month, to_month=to_month)


@router.get(
    "/breakdowns/{dimension}",
    response_model=BreakdownResponse,
    summary="Get dimensional breakdown for dashboard charts",
    description=(
        "Supported dimensions: `department`, `payment_status`, `city`, `insurance_provider`, "
        "`age_band`, `category`, `doctor_id`, `service_type`, `approval_status`."
    ),
    responses=error_responses(400, 401, 404),
)
def get_breakdown(
    dataset_id: uuid.UUID,
    dimension: str,
    user: CurrentUser,
    db: DbSession,
    from_month: FromMonth = None,
    to_month: ToMonth = None,
) -> BreakdownResponse:
    dataset = dataset_service.get_dataset_for_user(db, user, dataset_id)
    return analytics_service.build_breakdown(
        db, dataset.id, dimension, from_month=from_month, to_month=to_month
    )

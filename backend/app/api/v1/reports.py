"""Reports router: list reports, get full verified report detail, and download reproducible PDF."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.api.deps import CurrentUser, DbSession
from app.schemas.common import Page, PageParams, error_responses
from app.schemas.report import ReportDetailOut, ReportOut
from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get(
    "",
    response_model=Page[ReportOut],
    summary="List generated business intelligence reports",
    responses=error_responses(401),
)
def list_reports(
    user: CurrentUser,
    db: DbSession,
    page: Annotated[PageParams, Depends()],
    dataset_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[ReportOut]:
    items, total = report_service.list_reports(db, user, page, dataset_id=dataset_id)
    return Page[ReportOut](
        items=items,
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get(
    "/{report_id}",
    response_model=ReportDetailOut,
    summary="Get full report (8 sections, findings, verification appendix, and recommendations)",
    responses=error_responses(401, 404),
)
def get_report(report_id: uuid.UUID, user: CurrentUser, db: DbSession) -> ReportDetailOut:
    return report_service.get_report_detail(db, user, report_id)


@router.get(
    "/{report_id}/pdf",
    summary="Download the reproducible executive PDF report",
    description=(
        "Generates a professional PDF containing the cover, executive summary, KPI baseline "
        "table, embedded revenue/expense chart, all 8 sections, verified findings, "
        "recommendation approval table, and verification appendix."
    ),
    responses={
        200: {"content": {"application/pdf": {}}, "description": "PDF file"},
        **error_responses(401, 404),
    },
)
def download_report_pdf(report_id: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    pdf_bytes = report_service.render_report_pdf(db, user, report_id)
    filename = f"careops_report_{str(report_id)[:8]}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

"""Dataset upload, listing, detail, quality report, and deletion endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status

from app.api.deps import AppSettings, CurrentUser, DbSession, ManagerOrAdmin
from app.ingestion.reader import RawUploadFile
from app.schemas.common import Page, PageParams, error_responses
from app.schemas.dataset import DatasetDetailOut, DatasetOut, QualityReportOut
from app.services import dataset_service

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post(
    "",
    response_model=DatasetDetailOut,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest a healthcare dataset (.xlsx or 5 .csv files)",
    description=(
        "Validates file extensions and magic-byte signatures, rejects macros and formulas, "
        "cleans strings and dates, quarantines invalid rows with structured reasons, derives "
        "`doctors`, `suppliers`, and `vendors` dimensions, masks phone numbers to the last 4 "
        "digits, and loads everything in a single database transaction. Requires role `manager` "
        "or `admin`."
    ),
    responses=error_responses(401, 403, 413, 415, 422),
)
async def upload_dataset(
    files: Annotated[
        list[UploadFile],
        File(description="Single .xlsx workbook OR the 5 entity .csv files"),
    ],
    user: ManagerOrAdmin,
    db: DbSession,
    settings: AppSettings,
    name: Annotated[str | None, Form(max_length=200)] = None,
) -> DatasetDetailOut:
    raw_files = [RawUploadFile(filename=f.filename or "", content=await f.read()) for f in files]
    dataset = dataset_service.ingest_upload(db, settings, owner=user, name=name, files=raw_files)
    return DatasetDetailOut.model_validate(dataset)


@router.get(
    "",
    response_model=Page[DatasetOut],
    summary="List datasets",
    description="Managers and analysts see their own datasets; admins see all datasets.",
    responses=error_responses(401),
)
def list_datasets(
    user: CurrentUser, db: DbSession, page: Annotated[PageParams, Depends()]
) -> Page[DatasetOut]:
    items, total = dataset_service.list_datasets(db, user, page)
    return Page[DatasetOut](
        items=[DatasetOut.model_validate(d) for d in items],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.get(
    "/{dataset_id}",
    response_model=DatasetDetailOut,
    summary="Get dataset metadata and quality report",
    responses=error_responses(401, 404),
)
def get_dataset(dataset_id: uuid.UUID, user: CurrentUser, db: DbSession) -> DatasetDetailOut:
    dataset = dataset_service.get_dataset_for_user(db, user, dataset_id)
    return DatasetDetailOut.model_validate(dataset)


@router.get(
    "/{dataset_id}/quality-report",
    response_model=QualityReportOut,
    summary="Get the ingestion quality report for a dataset",
    responses=error_responses(401, 404),
)
def get_quality_report(dataset_id: uuid.UUID, user: CurrentUser, db: DbSession) -> QualityReportOut:
    dataset = dataset_service.get_dataset_for_user(db, user, dataset_id)
    return QualityReportOut.model_validate(dataset.quality_report)


@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a dataset and all its domain rows",
    responses=error_responses(401, 403, 404),
)
def delete_dataset(dataset_id: uuid.UUID, user: ManagerOrAdmin, db: DbSession) -> Response:
    dataset_service.delete_dataset(db, user, dataset_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

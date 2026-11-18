"""Pydantic schemas for dataset upload, listing, and quality reports."""

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import DatasetStatus


class QuarantinedSampleOut(BaseModel):
    entity: str
    row_number: int
    primary_key: str
    reason: str


class QualityWarningOut(BaseModel):
    code: str
    entity: str
    message: str
    duplicate_batch_count: int | None = None
    affected_items: int | None = None
    duplicate_batches: list[str] | None = None


class QualityReportOut(BaseModel):
    period_start: str = Field(examples=["2026-05-01"])
    period_end: str = Field(examples=["2026-10-31"])
    rows_read: dict[str, int]
    rows_loaded: dict[str, int]
    total_read: int
    total_loaded: int
    total_quarantined: int
    quarantined_by_entity: dict[str, int]
    quarantined_by_reason: dict[str, int]
    quarantined_samples: list[dict[str, Any]]
    derived_dimensions: dict[str, int]
    warnings: list[QualityWarningOut] = Field(default_factory=list)


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    source_filename: str
    status: DatasetStatus
    row_counts: dict[str, int]
    period_start: date | None
    period_end: date | None
    created_at: datetime


class DatasetDetailOut(DatasetOut):
    quality_report: QualityReportOut

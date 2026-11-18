"""Transactional bulk loader for cleaned healthcare datasets."""

import uuid

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db.models import (
    Appointment,
    Dataset,
    DatasetStatus,
    Doctor,
    Expense,
    Invoice,
    MedicineItem,
    Patient,
    Supplier,
    Vendor,
)
from app.ingestion.validator import CleanedDataset

log = get_logger(__name__)


def _with_dataset_id(rows: list[dict], dataset_id: uuid.UUID) -> list[dict]:
    return [{"dataset_id": dataset_id, **row} for row in rows]


def persist_cleaned_dataset(
    db: Session,
    *,
    owner_id: uuid.UUID,
    name: str,
    source_filename: str,
    cleaned: CleanedDataset,
) -> Dataset:
    """Insert the Dataset metadata, derived dimensions, and domain rows in a single transaction."""
    dataset = Dataset(
        owner_id=owner_id,
        name=name,
        source_filename=source_filename,
        status=DatasetStatus.READY,
        row_counts=cleaned.row_counts,
        quality_report=cleaned.quality_report,
        period_start=cleaned.period_start,
        period_end=cleaned.period_end,
    )
    try:
        db.add(dataset)
        db.flush()
        ds_id = dataset.id

        # Dimensions first so composite FKs on fact tables are satisfied.
        if cleaned.doctors:
            db.execute(insert(Doctor), _with_dataset_id(cleaned.doctors, ds_id))
        if cleaned.suppliers:
            db.execute(insert(Supplier), _with_dataset_id(cleaned.suppliers, ds_id))
        if cleaned.vendors:
            db.execute(insert(Vendor), _with_dataset_id(cleaned.vendors, ds_id))
        if cleaned.patients:
            db.execute(insert(Patient), _with_dataset_id(cleaned.patients, ds_id))

        if cleaned.appointments:
            db.execute(insert(Appointment), _with_dataset_id(cleaned.appointments, ds_id))
        if cleaned.invoices:
            db.execute(insert(Invoice), _with_dataset_id(cleaned.invoices, ds_id))
        if cleaned.medicine_items:
            db.execute(insert(MedicineItem), _with_dataset_id(cleaned.medicine_items, ds_id))
        if cleaned.expenses:
            db.execute(insert(Expense), _with_dataset_id(cleaned.expenses, ds_id))

        db.commit()
        db.refresh(dataset)
        log.info(
            "dataset_ingested",
            dataset_id=str(dataset.id),
            owner_id=str(owner_id),
            total_loaded=cleaned.quality_report.get("total_loaded"),
            total_quarantined=cleaned.quality_report.get("total_quarantined"),
        )
        return dataset
    except Exception:
        db.rollback()
        raise

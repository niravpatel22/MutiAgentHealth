"""Dataset management service: upload ingestion, scoped listing, detail, and deletion."""

import gc
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import ensure_owner_or_admin
from app.core.config import Settings
from app.core.errors import NotFoundError
from app.db.models import Dataset, Role, User
from app.ingestion.loader import persist_cleaned_dataset
from app.ingestion.reader import RawUploadFile, read_upload
from app.ingestion.validator import validate_and_clean
from app.schemas.common import PageParams


def ingest_upload(
    db: Session,
    settings: Settings,
    *,
    owner: User,
    name: str | None,
    files: list[RawUploadFile],
) -> Dataset:
    frames, source_filename = read_upload(
        files, max_mb=settings.max_upload_mb, max_rows=settings.max_upload_rows
    )
    cleaned = validate_and_clean(frames)
    del frames
    gc.collect()
    dataset_name = (name or "").strip() or Path(files[0].filename).stem or "Healthcare Dataset"
    ds = persist_cleaned_dataset(
        db,
        owner_id=owner.id,
        name=dataset_name[:200],
        source_filename=source_filename[:255],
        cleaned=cleaned,
    )
    del cleaned
    gc.collect()
    return ds


def list_datasets(db: Session, user: User, page: PageParams) -> tuple[list[Dataset], int]:
    base = select(Dataset)
    count_stmt = select(func.count()).select_from(Dataset)
    if user.role != Role.ADMIN:
        base = base.where(Dataset.owner_id == user.id)
        count_stmt = count_stmt.where(Dataset.owner_id == user.id)
    total = int(db.scalar(count_stmt) or 0)
    items = list(
        db.scalars(
            base.order_by(Dataset.created_at.desc()).offset(page.offset).limit(page.page_size)
        ).all()
    )
    return items, total


def get_dataset_for_user(db: Session, user: User, dataset_id: uuid.UUID) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise NotFoundError("Dataset not found")
    ensure_owner_or_admin(user, dataset.owner_id, "Dataset")
    return dataset


def delete_dataset(db: Session, user: User, dataset_id: uuid.UUID) -> None:
    dataset = get_dataset_for_user(db, user, dataset_id)
    db.delete(dataset)
    db.commit()

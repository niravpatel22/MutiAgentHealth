"""Hardened upload reader for .xlsx workbooks and multi-file .csv uploads.

Security rules:
- Check both file extension and magic-byte content signature.
- Reject macros (vbaProject.bin / .xlsm), zip-bombs, binary masquerading as CSV, and oversized
  uploads (default 10 MB total, 100,000 rows total).
- Read Excel strictly with openpyxl in ``read_only=True, data_only=True`` mode; never evaluate
  formulas or call ``eval``.
"""

import io
import zipfile
from dataclasses import dataclass

import openpyxl
import pandas as pd

from app.core.errors import AppError

REQUIRED_ENTITIES: tuple[str, ...] = (
    "Patients",
    "Appointments",
    "Billing",
    "Medicine_Inventory",
    "Expenses",
)

CSV_NAME_TO_ENTITY: dict[str, str] = {
    "patients.csv": "Patients",
    "appointments.csv": "Appointments",
    "billing.csv": "Billing",
    "medicine_inventory.csv": "Medicine_Inventory",
    "expenses.csv": "Expenses",
}

_ZIP_MAGIC = b"PK\x03\x04"
_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_MAX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024  # 50 MB zip-bomb guard


class UploadValidationError(AppError):
    status_code = 422
    code = "invalid_upload"


@dataclass(frozen=True)
class RawUploadFile:
    filename: str
    content: bytes


def read_upload(
    files: list[RawUploadFile],
    *,
    max_mb: int = 10,
    max_rows: int = 100_000,
) -> tuple[dict[str, pd.DataFrame], str]:
    """Parse and return ``(frames_by_entity, source_filename)``."""
    if not files:
        raise UploadValidationError("No files uploaded")

    max_bytes = max_mb * 1024 * 1024
    total_bytes = sum(len(f.content) for f in files)
    if total_bytes == 0:
        raise UploadValidationError("Uploaded file is empty")
    if total_bytes > max_bytes:
        raise UploadValidationError(
            f"Upload exceeds the {max_mb} MB limit",
            details={"total_bytes": total_bytes, "max_bytes": max_bytes},
        )

    lower_names = [(f.filename or "").strip().lower() for f in files]
    if len(files) == 1 and lower_names[0].endswith(".xlsx"):
        frames = _read_xlsx(files[0].content, max_rows=max_rows)
        return frames, files[0].filename

    if any(n.endswith((".xlsm", ".xlsb", ".xls")) for n in lower_names):
        raise UploadValidationError("Macro-enabled or legacy Excel files are not permitted")

    if all(n.endswith(".csv") for n in lower_names):
        frames = _read_csv_bundle(files, max_rows=max_rows)
        return frames, ", ".join(sorted(f.filename for f in files))

    raise UploadValidationError(
        "Upload either a single .xlsx workbook or the five entity .csv files "
        "(patients.csv, appointments.csv, billing.csv, medicine_inventory.csv, expenses.csv)"
    )


def _read_xlsx(content: bytes, *, max_rows: int) -> dict[str, pd.DataFrame]:
    if content.startswith(_OLE_MAGIC) or not content.startswith(_ZIP_MAGIC):
        raise UploadValidationError("File content is not a valid .xlsx (OOXML) archive")

    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            names = zf.namelist()
            if any("vbaproject" in n.lower() or n.lower().endswith(".bin") for n in names):
                raise UploadValidationError("Excel macros (VBA) are not permitted")
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > _MAX_UNCOMPRESSED_BYTES:
                raise UploadValidationError("Uncompressed workbook exceeds safety limit")
            if "xl/workbook.xml" not in names:
                raise UploadValidationError("Archive is not a valid Excel workbook")
    except zipfile.BadZipFile as exc:
        raise UploadValidationError("Corrupted .xlsx archive") from exc

    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise UploadValidationError("Could not parse .xlsx workbook") from exc

    try:
        sheet_names = set(wb.sheetnames)
        missing = [s for s in REQUIRED_ENTITIES if s not in sheet_names]
        if missing:
            raise UploadValidationError(
                "Workbook is missing required sheets", details={"missing_sheets": missing}
            )

        frames: dict[str, pd.DataFrame] = {}
        total_rows = 0
        for entity in REQUIRED_ENTITIES:
            ws = wb[entity]
            rows_iter = ws.iter_rows(values_only=True)
            header_row = next(rows_iter, None)
            if not header_row:
                raise UploadValidationError(f"Sheet '{entity}' is empty")
            headers = [str(h).strip() if h is not None else "" for h in header_row]
            data_rows: list[tuple[object, ...]] = []
            for row in rows_iter:
                if row is None or all(cell is None or str(cell).strip() == "" for cell in row):
                    continue
                total_rows += 1
                if total_rows > max_rows:
                    raise UploadValidationError(
                        f"Upload exceeds the {max_rows:,}-row limit",
                        details={"max_rows": max_rows},
                    )
                data_rows.append(row)
            frames[entity] = pd.DataFrame(data_rows, columns=headers)
        return frames
    finally:
        wb.close()


def _read_csv_bundle(files: list[RawUploadFile], *, max_rows: int) -> dict[str, pd.DataFrame]:
    by_name = {(f.filename or "").strip().lower().rsplit("/", 1)[-1]: f.content for f in files}
    missing = [csv_name for csv_name in CSV_NAME_TO_ENTITY if csv_name not in by_name]
    if missing:
        raise UploadValidationError(
            "CSV upload requires all five entity files",
            details={"missing_files": missing, "expected": sorted(CSV_NAME_TO_ENTITY)},
        )

    frames: dict[str, pd.DataFrame] = {}
    total_rows = 0
    for csv_name, entity in CSV_NAME_TO_ENTITY.items():
        raw = by_name[csv_name]
        if raw.startswith((_ZIP_MAGIC, _OLE_MAGIC, b"%PDF", b"\x89PNG")) or b"\x00" in raw[:4096]:
            raise UploadValidationError(f"File '{csv_name}' is not plain UTF-8 text")
        try:
            text = raw.decode("utf-8-sig")
            df = pd.read_csv(io.StringIO(text), dtype=object)
        except Exception as exc:
            raise UploadValidationError(f"Could not parse '{csv_name}'") from exc
        total_rows += len(df)
        if total_rows > max_rows:
            raise UploadValidationError(
                f"Upload exceeds the {max_rows:,}-row limit", details={"max_rows": max_rows}
            )
        df.columns = [str(c).strip() for c in df.columns]
        frames[entity] = df
    return frames

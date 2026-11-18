"""Validation, cleaning, quarantine, derived dimensions, and quality report generation."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import pandas as pd

from app.ingestion.reader import REQUIRED_ENTITIES, UploadValidationError

PERIOD_START = date(2026, 5, 1)
PERIOD_END = date(2026, 10, 31)
TWO_PLACES = Decimal("0.01")
NET_TOLERANCE = Decimal("0.02")

REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "Patients": (
        "patient_id",
        "patient_name",
        "age",
        "gender",
        "city",
        "phone",
        "registration_date",
        "insurance_provider",
    ),
    "Appointments": (
        "appointment_id",
        "patient_id",
        "doctor_id",
        "department",
        "appointment_date",
        "appointment_type",
        "status",
        "wait_time_minutes",
        "consultation_fee",
    ),
    "Billing": (
        "invoice_id",
        "patient_id",
        "invoice_date",
        "service_type",
        "gross_amount",
        "discount",
        "net_amount",
        "payment_status",
        "payment_mode",
    ),
    "Medicine_Inventory": (
        "item_id",
        "medicine_name",
        "batch_no",
        "category",
        "stock_on_hand",
        "reorder_level",
        "unit_cost",
        "expiry_date",
        "supplier_id",
    ),
    "Expenses": (
        "expense_id",
        "expense_date",
        "category",
        "department",
        "amount",
        "vendor",
        "approval_status",
    ),
}

# Canonical casing maps for categorical enums.
GENDER_MAP = {"female": "Female", "male": "Male", "other": "Other"}
APPT_STATUS_MAP = {
    "completed": "Completed",
    "scheduled": "Scheduled",
    "cancelled": "Cancelled",
    "no show": "No Show",
    "no-show": "No Show",
    "noshow": "No Show",
}
APPT_TYPE_MAP = {
    "consultation": "Consultation",
    "diagnostic": "Diagnostic",
    "follow-up": "Follow-up",
    "followup": "Follow-up",
}
PAYMENT_STATUS_MAP = {
    "paid": "Paid",
    "partially paid": "Partially Paid",
    "pending": "Pending",
}
PAYMENT_MODE_MAP = {"card": "Card", "cash": "Cash", "insurance": "Insurance", "upi": "UPI"}
SERVICE_TYPE_MAP = {
    "consultation": "Consultation",
    "imaging": "Imaging",
    "lab test": "Lab Test",
    "pharmacy": "Pharmacy",
    "room charges": "Room Charges",
    "surgery": "Surgery",
}
MED_CATEGORY_MAP = {
    "capsule": "Capsule",
    "consumable": "Consumable",
    "injection": "Injection",
    "syrup": "Syrup",
    "tablet": "Tablet",
}
EXPENSE_CATEGORY_MAP = {
    "equipment": "Equipment",
    "housekeeping": "Housekeeping",
    "maintenance": "Maintenance",
    "medical supplies": "Medical Supplies",
    "staff salary": "Staff Salary",
    "utilities": "Utilities",
}
APPROVAL_STATUS_MAP = {
    "approved": "Approved",
    "pending": "Pending",
    "rejected": "Rejected",
}
DEPARTMENT_MAP = {
    "cardiology": "Cardiology",
    "dermatology": "Dermatology",
    "ent": "ENT",
    "general medicine": "General Medicine",
    "gynecology": "Gynecology",
    "neurology": "Neurology",
    "orthopedics": "Orthopedics",
    "pediatrics": "Pediatrics",
}


def age_band_for(age: int) -> str:
    if age <= 17:
        return "0-17"
    if age <= 34:
        return "18-34"
    if age <= 54:
        return "35-54"
    if age <= 74:
        return "55-74"
    return "75+"


def mask_phone(digits: str) -> str:
    return f"******{digits[-4:]}"


def _clean_str(val: object) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def _parse_int(val: object) -> int | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, bool):
        return None
    if isinstance(val, int):
        return int(val)
    text = str(val).strip()
    if not text:
        return None
    try:
        dec = Decimal(text)
        if dec != dec.to_integral_value():
            return None
        return int(dec)
    except InvalidOperation:
        return None


def _parse_money(val: object) -> Decimal | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, bool):
        return None
    text = str(val).strip()
    if not text:
        return None
    try:
        return Decimal(text).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def _parse_date(val: object) -> date | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    text = str(val).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        try:
            return pd.to_datetime(text).date()
        except Exception:
            return None


@dataclass
class QuarantinedRow:
    entity: str
    row_number: int
    primary_key: str
    reason: str


@dataclass
class CleanedDataset:
    patients: list[dict[str, Any]] = field(default_factory=list)
    doctors: list[dict[str, Any]] = field(default_factory=list)
    suppliers: list[dict[str, Any]] = field(default_factory=list)
    vendors: list[dict[str, Any]] = field(default_factory=list)
    appointments: list[dict[str, Any]] = field(default_factory=list)
    invoices: list[dict[str, Any]] = field(default_factory=list)
    medicine_items: list[dict[str, Any]] = field(default_factory=list)
    expenses: list[dict[str, Any]] = field(default_factory=list)
    row_counts: dict[str, int] = field(default_factory=dict)
    quality_report: dict[str, Any] = field(default_factory=dict)
    period_start: date = PERIOD_START
    period_end: date = PERIOD_END


def validate_and_clean(frames: dict[str, pd.DataFrame]) -> CleanedDataset:
    """Validate all five sheets, quarantine bad rows with reasons, and derive dimensions."""
    for entity in REQUIRED_ENTITIES:
        if entity not in frames:
            raise UploadValidationError(
                f"Missing required sheet '{entity}'", details={"missing_sheets": [entity]}
            )
        cols = set(frames[entity].columns)
        missing_cols = [c for c in REQUIRED_COLUMNS[entity] if c not in cols]
        if missing_cols:
            raise UploadValidationError(
                f"Sheet '{entity}' is missing required columns",
                details={"sheet": entity, "missing_columns": missing_cols},
            )

    quarantined: list[QuarantinedRow] = []
    warnings: list[dict[str, Any]] = []

    patients, valid_patient_ids = _clean_patients(frames["Patients"], quarantined)
    appointments, doctors = _clean_appointments(
        frames["Appointments"], valid_patient_ids, quarantined
    )
    invoices = _clean_billing(frames["Billing"], valid_patient_ids, quarantined)
    medicine_items, suppliers, dup_batch_warning = _clean_inventory(
        frames["Medicine_Inventory"], quarantined
    )
    if dup_batch_warning:
        warnings.append(dup_batch_warning)
    expenses, vendors = _clean_expenses(frames["Expenses"], quarantined)

    rows_read = {entity: len(frames[entity]) for entity in REQUIRED_ENTITIES}
    rows_loaded = {
        "Patients": len(patients),
        "Appointments": len(appointments),
        "Billing": len(invoices),
        "Medicine_Inventory": len(medicine_items),
        "Expenses": len(expenses),
    }

    if sum(rows_loaded.values()) == 0:
        raise UploadValidationError("No valid rows remained after validation")

    by_reason = Counter(f"{q.entity}:{q.reason}" for q in quarantined)
    by_entity = Counter(q.entity for q in quarantined)

    quality_report: dict[str, Any] = {
        "period_start": PERIOD_START.isoformat(),
        "period_end": PERIOD_END.isoformat(),
        "rows_read": rows_read,
        "rows_loaded": rows_loaded,
        "total_read": sum(rows_read.values()),
        "total_loaded": sum(rows_loaded.values()),
        "total_quarantined": len(quarantined),
        "quarantined_by_entity": dict(by_entity),
        "quarantined_by_reason": dict(by_reason),
        "quarantined_samples": [
            {
                "entity": q.entity,
                "row_number": q.row_number,
                "primary_key": q.primary_key,
                "reason": q.reason,
            }
            for q in quarantined[:100]
        ],
        "derived_dimensions": {
            "doctors": len(doctors),
            "suppliers": len(suppliers),
            "vendors": len(vendors),
        },
        "warnings": warnings,
    }

    return CleanedDataset(
        patients=patients,
        doctors=doctors,
        suppliers=suppliers,
        vendors=vendors,
        appointments=appointments,
        invoices=invoices,
        medicine_items=medicine_items,
        expenses=expenses,
        row_counts=rows_loaded,
        quality_report=quality_report,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )


def _clean_patients(
    df: pd.DataFrame, quarantined: list[QuarantinedRow]
) -> tuple[list[dict[str, Any]], set[str]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for idx, rec in enumerate(df.to_dict(orient="records"), start=2):
        pid = _clean_str(rec.get("patient_id"))
        if not pid:
            quarantined.append(QuarantinedRow("Patients", idx, "", "missing_primary_key"))
            continue
        if pid in seen:
            quarantined.append(QuarantinedRow("Patients", idx, pid, "duplicate_primary_key"))
            continue

        name = _clean_str(rec.get("patient_name"))
        city = _clean_str(rec.get("city")).title()
        insurance = _clean_str(rec.get("insurance_provider"))
        gender = GENDER_MAP.get(_clean_str(rec.get("gender")).lower())
        age = _parse_int(rec.get("age"))
        phone_int = _parse_int(rec.get("phone"))
        reg_date = _parse_date(rec.get("registration_date"))

        if not name or not city or not insurance:
            quarantined.append(QuarantinedRow("Patients", idx, pid, "missing_required_field"))
            continue
        if gender is None:
            quarantined.append(QuarantinedRow("Patients", idx, pid, "invalid_gender"))
            continue
        if age is None or not (0 <= age <= 120):
            quarantined.append(QuarantinedRow("Patients", idx, pid, "invalid_age"))
            continue
        phone_str = str(phone_int) if phone_int is not None else ""
        if len(phone_str) != 10 or not phone_str.isdigit():
            quarantined.append(QuarantinedRow("Patients", idx, pid, "invalid_phone"))
            continue
        if reg_date is None:
            quarantined.append(QuarantinedRow("Patients", idx, pid, "invalid_date"))
            continue
        if not (PERIOD_START <= reg_date <= PERIOD_END):
            quarantined.append(QuarantinedRow("Patients", idx, pid, "date_outside_period"))
            continue

        seen.add(pid)
        rows.append(
            {
                "patient_id": pid,
                "patient_name": name,
                "age": age,
                "age_band": age_band_for(age),
                "gender": gender,
                "city": city,
                "phone_masked": mask_phone(phone_str),
                "registration_date": reg_date,
                "registration_month": reg_date.strftime("%Y-%m"),
                "insurance_provider": insurance,
            }
        )
    return rows, seen


def _clean_appointments(
    df: pd.DataFrame, valid_patients: set[str], quarantined: list[QuarantinedRow]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    doctor_depts: dict[str, Counter[str]] = {}

    for idx, rec in enumerate(df.to_dict(orient="records"), start=2):
        aid = _clean_str(rec.get("appointment_id"))
        if not aid:
            quarantined.append(QuarantinedRow("Appointments", idx, "", "missing_primary_key"))
            continue
        if aid in seen:
            quarantined.append(QuarantinedRow("Appointments", idx, aid, "duplicate_primary_key"))
            continue

        pid = _clean_str(rec.get("patient_id"))
        did = _clean_str(rec.get("doctor_id"))
        dept = DEPARTMENT_MAP.get(_clean_str(rec.get("department")).lower())
        appt_type = APPT_TYPE_MAP.get(_clean_str(rec.get("appointment_type")).lower())
        status = APPT_STATUS_MAP.get(_clean_str(rec.get("status")).lower())
        appt_date = _parse_date(rec.get("appointment_date"))
        wait = _parse_int(rec.get("wait_time_minutes"))
        fee = _parse_money(rec.get("consultation_fee"))

        if not pid or not did:
            quarantined.append(QuarantinedRow("Appointments", idx, aid, "missing_required_field"))
            continue
        if pid not in valid_patients:
            quarantined.append(QuarantinedRow("Appointments", idx, aid, "orphan_patient_id"))
            continue
        if dept is None:
            quarantined.append(QuarantinedRow("Appointments", idx, aid, "invalid_department"))
            continue
        if appt_type is None:
            quarantined.append(QuarantinedRow("Appointments", idx, aid, "invalid_appointment_type"))
            continue
        if status is None:
            quarantined.append(QuarantinedRow("Appointments", idx, aid, "invalid_status"))
            continue
        if appt_date is None:
            quarantined.append(QuarantinedRow("Appointments", idx, aid, "invalid_date"))
            continue
        if not (PERIOD_START <= appt_date <= PERIOD_END):
            quarantined.append(QuarantinedRow("Appointments", idx, aid, "date_outside_period"))
            continue
        if wait is None or wait < 0:
            quarantined.append(QuarantinedRow("Appointments", idx, aid, "invalid_wait_time"))
            continue
        if fee is None or fee < Decimal("0"):
            quarantined.append(QuarantinedRow("Appointments", idx, aid, "negative_amount"))
            continue

        seen.add(aid)
        doctor_depts.setdefault(did, Counter())[dept] += 1
        rows.append(
            {
                "appointment_id": aid,
                "patient_id": pid,
                "doctor_id": did,
                "department": dept,
                "appointment_date": appt_date,
                "month": appt_date.strftime("%Y-%m"),
                "appointment_type": appt_type,
                "status": status,
                "wait_time_minutes": wait,
                "consultation_fee": fee,
            }
        )

    doctors = [
        {"doctor_id": did, "primary_department": counts.most_common(1)[0][0]}
        for did, counts in sorted(doctor_depts.items())
    ]
    return rows, doctors


def _clean_billing(
    df: pd.DataFrame, valid_patients: set[str], quarantined: list[QuarantinedRow]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for idx, rec in enumerate(df.to_dict(orient="records"), start=2):
        iid = _clean_str(rec.get("invoice_id"))
        if not iid:
            quarantined.append(QuarantinedRow("Billing", idx, "", "missing_primary_key"))
            continue
        if iid in seen:
            quarantined.append(QuarantinedRow("Billing", idx, iid, "duplicate_primary_key"))
            continue

        pid = _clean_str(rec.get("patient_id"))
        inv_date = _parse_date(rec.get("invoice_date"))
        stype = SERVICE_TYPE_MAP.get(_clean_str(rec.get("service_type")).lower())
        pstatus = PAYMENT_STATUS_MAP.get(_clean_str(rec.get("payment_status")).lower())
        pmode = PAYMENT_MODE_MAP.get(_clean_str(rec.get("payment_mode")).lower())
        gross = _parse_money(rec.get("gross_amount"))
        disc = _parse_money(rec.get("discount"))
        net = _parse_money(rec.get("net_amount"))

        if not pid:
            quarantined.append(QuarantinedRow("Billing", idx, iid, "missing_required_field"))
            continue
        if pid not in valid_patients:
            quarantined.append(QuarantinedRow("Billing", idx, iid, "orphan_patient_id"))
            continue
        if inv_date is None:
            quarantined.append(QuarantinedRow("Billing", idx, iid, "invalid_date"))
            continue
        if not (PERIOD_START <= inv_date <= PERIOD_END):
            quarantined.append(QuarantinedRow("Billing", idx, iid, "date_outside_period"))
            continue
        if stype is None:
            quarantined.append(QuarantinedRow("Billing", idx, iid, "invalid_service_type"))
            continue
        if pstatus is None:
            quarantined.append(QuarantinedRow("Billing", idx, iid, "invalid_payment_status"))
            continue
        if pmode is None:
            quarantined.append(QuarantinedRow("Billing", idx, iid, "invalid_payment_mode"))
            continue
        if gross is None or disc is None or net is None or min(gross, disc, net) < Decimal("0"):
            quarantined.append(QuarantinedRow("Billing", idx, iid, "negative_amount"))
            continue
        if abs(net - (gross - disc)) > NET_TOLERANCE:
            quarantined.append(QuarantinedRow("Billing", idx, iid, "net_amount_mismatch"))
            continue

        seen.add(iid)
        rows.append(
            {
                "invoice_id": iid,
                "patient_id": pid,
                "invoice_date": inv_date,
                "month": inv_date.strftime("%Y-%m"),
                "service_type": stype,
                "gross_amount": gross,
                "discount": disc,
                "net_amount": net,
                "payment_status": pstatus,
                "payment_mode": pmode,
            }
        )
    return rows


def _clean_inventory(
    df: pd.DataFrame, quarantined: list[QuarantinedRow]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any] | None]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    supplier_ids: set[str] = set()

    for idx, rec in enumerate(df.to_dict(orient="records"), start=2):
        mid = _clean_str(rec.get("item_id"))
        if not mid:
            quarantined.append(QuarantinedRow("Medicine_Inventory", idx, "", "missing_primary_key"))
            continue
        if mid in seen:
            quarantined.append(
                QuarantinedRow("Medicine_Inventory", idx, mid, "duplicate_primary_key")
            )
            continue

        mname = _clean_str(rec.get("medicine_name"))
        batch = _clean_str(rec.get("batch_no"))
        cat = MED_CATEGORY_MAP.get(_clean_str(rec.get("category")).lower())
        stock = _parse_int(rec.get("stock_on_hand"))
        reorder = _parse_int(rec.get("reorder_level"))
        cost = _parse_money(rec.get("unit_cost"))
        exp_date = _parse_date(rec.get("expiry_date"))
        sup = _clean_str(rec.get("supplier_id"))

        if not mname or not batch or not sup:
            quarantined.append(
                QuarantinedRow("Medicine_Inventory", idx, mid, "missing_required_field")
            )
            continue
        if cat is None:
            quarantined.append(QuarantinedRow("Medicine_Inventory", idx, mid, "invalid_category"))
            continue
        if stock is None or reorder is None or stock < 0 or reorder < 0:
            quarantined.append(QuarantinedRow("Medicine_Inventory", idx, mid, "negative_stock"))
            continue
        if cost is None or cost < Decimal("0"):
            quarantined.append(QuarantinedRow("Medicine_Inventory", idx, mid, "negative_amount"))
            continue
        if exp_date is None:
            quarantined.append(QuarantinedRow("Medicine_Inventory", idx, mid, "invalid_date"))
            continue

        seen.add(mid)
        supplier_ids.add(sup)
        rows.append(
            {
                "item_id": mid,
                "medicine_name": mname,
                "batch_no": batch,
                "is_duplicate_batch": False,
                "category": cat,
                "stock_on_hand": stock,
                "reorder_level": reorder,
                "unit_cost": cost,
                "expiry_date": exp_date,
                "supplier_id": sup,
            }
        )

    batch_counts = Counter(r["batch_no"] for r in rows)
    dup_batches = sorted(b for b, c in batch_counts.items() if c > 1)
    affected = 0
    for r in rows:
        if batch_counts[r["batch_no"]] > 1:
            r["is_duplicate_batch"] = True
            affected += 1

    warning = None
    if dup_batches:
        warning = {
            "code": "duplicate_batch_no",
            "entity": "Medicine_Inventory",
            "message": (
                f"{len(dup_batches)} batch_no values appear more than once across {affected} "
                "inventory items (flagged, kept because item_id is unique)."
            ),
            "duplicate_batch_count": len(dup_batches),
            "affected_items": affected,
            "duplicate_batches": dup_batches,
        }

    suppliers = [{"supplier_id": s} for s in sorted(supplier_ids)]
    return rows, suppliers, warning


def _clean_expenses(
    df: pd.DataFrame, quarantined: list[QuarantinedRow]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    vendor_names: set[str] = set()

    for idx, rec in enumerate(df.to_dict(orient="records"), start=2):
        eid = _clean_str(rec.get("expense_id"))
        if not eid:
            quarantined.append(QuarantinedRow("Expenses", idx, "", "missing_primary_key"))
            continue
        if eid in seen:
            quarantined.append(QuarantinedRow("Expenses", idx, eid, "duplicate_primary_key"))
            continue

        exp_date = _parse_date(rec.get("expense_date"))
        cat = EXPENSE_CATEGORY_MAP.get(_clean_str(rec.get("category")).lower())
        dept = DEPARTMENT_MAP.get(_clean_str(rec.get("department")).lower())
        amount = _parse_money(rec.get("amount"))
        vendor = _clean_str(rec.get("vendor"))
        approval = APPROVAL_STATUS_MAP.get(_clean_str(rec.get("approval_status")).lower())

        if not vendor:
            quarantined.append(QuarantinedRow("Expenses", idx, eid, "missing_required_field"))
            continue
        if exp_date is None:
            quarantined.append(QuarantinedRow("Expenses", idx, eid, "invalid_date"))
            continue
        if not (PERIOD_START <= exp_date <= PERIOD_END):
            quarantined.append(QuarantinedRow("Expenses", idx, eid, "date_outside_period"))
            continue
        if cat is None:
            quarantined.append(QuarantinedRow("Expenses", idx, eid, "invalid_category"))
            continue
        if dept is None:
            quarantined.append(QuarantinedRow("Expenses", idx, eid, "invalid_department"))
            continue
        if approval is None:
            quarantined.append(QuarantinedRow("Expenses", idx, eid, "invalid_approval_status"))
            continue
        if amount is None or amount < Decimal("0"):
            quarantined.append(QuarantinedRow("Expenses", idx, eid, "negative_amount"))
            continue

        seen.add(eid)
        vendor_names.add(vendor)
        rows.append(
            {
                "expense_id": eid,
                "expense_date": exp_date,
                "month": exp_date.strftime("%Y-%m"),
                "category": cat,
                "department": dept,
                "amount": amount,
                "vendor": vendor,
                "approval_status": approval,
            }
        )

    vendors = [{"vendor_name": v} for v in sorted(vendor_names)]
    return rows, vendors

"""Deterministic metrics registry and engine (single source of truth).

Every number in the dashboard, AI agent tools, verifier, chat, and PDF report comes from this
module. Every metric function returns::

    {
        "key": str,
        "value": int | float,
        "unit": "count" | "INR" | "percent" | "minutes",
        "definition": str,
        "basis": str,
        "as_of": "2026-10-31",
        "dataset_id": str,
    }
"""

import math
import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import Select, case, distinct, func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.db.models import Appointment, Expense, Invoice, MedicineItem, Patient

AS_OF_DATE = date(2026, 10, 31)
EXPIRY_HORIZON_DAYS = 90
EXPIRY_CUTOFF = AS_OF_DATE + timedelta(days=EXPIRY_HORIZON_DAYS)  # 2027-01-29 (strict < cutoff)

Unit = Literal["count", "INR", "percent", "minutes"]


class UnknownMetricError(AppError):
    status_code = 400
    code = "unknown_metric"


@dataclass(frozen=True)
class MetricSpec:
    key: str
    unit: Unit
    definition: str
    basis: str
    dimensions: tuple[str, ...] = ()
    supports_monthly: bool = False


METRIC_SPECS: dict[str, MetricSpec] = {
    # ---- Volume & service ----
    "appointments.total": MetricSpec(
        key="appointments.total",
        unit="count",
        definition="Total appointments recorded across all statuses.",
        basis="all_appointments",
        dimensions=("month", "department", "appointment_type", "status"),
        supports_monthly=True,
    ),
    "appointments.completed": MetricSpec(
        key="appointments.completed",
        unit="count",
        definition="Appointments with status = Completed.",
        basis="completed_appointments",
        dimensions=("month", "department", "appointment_type"),
        supports_monthly=True,
    ),
    "appointments.scheduled": MetricSpec(
        key="appointments.scheduled",
        unit="count",
        definition="Appointments with status = Scheduled (treated as future pipeline, excluded from outcome rates).",
        basis="scheduled_pipeline",
        dimensions=("month", "department", "appointment_type"),
        supports_monthly=True,
    ),
    "appointments.cancelled": MetricSpec(
        key="appointments.cancelled",
        unit="count",
        definition="Appointments with status = Cancelled.",
        basis="cancelled_appointments",
        dimensions=("month", "department", "appointment_type"),
        supports_monthly=True,
    ),
    "appointments.no_show": MetricSpec(
        key="appointments.no_show",
        unit="count",
        definition="Appointments with status = No Show.",
        basis="no_show_appointments",
        dimensions=("month", "department", "appointment_type"),
        supports_monthly=True,
    ),
    "appointments.completion_rate": MetricSpec(
        key="appointments.completion_rate",
        unit="percent",
        definition="Completed appointments as a percentage of resolved appointments (Completed + Cancelled + No Show; Scheduled excluded).",
        basis="resolved_appointments_excluding_scheduled",
        dimensions=("month", "department"),
        supports_monthly=True,
    ),
    "appointments.cancellation_rate": MetricSpec(
        key="appointments.cancellation_rate",
        unit="percent",
        definition="Cancelled appointments as a percentage of resolved appointments (Scheduled excluded from denominator).",
        basis="resolved_appointments_excluding_scheduled",
        dimensions=("month", "department"),
        supports_monthly=True,
    ),
    "appointments.no_show_rate": MetricSpec(
        key="appointments.no_show_rate",
        unit="percent",
        definition="No-show appointments as a percentage of resolved appointments (Scheduled excluded from denominator).",
        basis="resolved_appointments_excluding_scheduled",
        dimensions=("month", "department", "insurance_provider", "age_band"),
        supports_monthly=True,
    ),
    "appointments.avg_wait_minutes": MetricSpec(
        key="appointments.avg_wait_minutes",
        unit="minutes",
        definition="Arithmetic mean of appointment wait_time_minutes.",
        basis="all_appointments",
        dimensions=("month", "department"),
        supports_monthly=True,
    ),
    "appointments.wait_over_60_share": MetricSpec(
        key="appointments.wait_over_60_share",
        unit="percent",
        definition="Percentage of appointments with wait_time_minutes > 60.",
        basis="all_appointments",
        dimensions=("month", "department"),
        supports_monthly=True,
    ),
    # ---- Revenue & finance ----
    "finance.net_revenue": MetricSpec(
        key="finance.net_revenue",
        unit="INR",
        definition="Sum of Billing.net_amount (gross_amount minus discount). Appointments.consultation_fee is excluded to prevent double counting.",
        basis="invoiced_billing_net_amount_only",
        dimensions=(
            "month",
            "service_type",
            "payment_status",
            "payment_mode",
            "insurance_provider",
        ),
        supports_monthly=True,
    ),
    "finance.gross_revenue": MetricSpec(
        key="finance.gross_revenue",
        unit="INR",
        definition="Sum of Billing.gross_amount before discounts.",
        basis="invoiced_billing_gross_amount",
        dimensions=("month", "service_type"),
        supports_monthly=True,
    ),
    "finance.total_discount": MetricSpec(
        key="finance.total_discount",
        unit="INR",
        definition="Sum of Billing.discount across all invoices.",
        basis="invoiced_billing_discount",
        dimensions=("month", "service_type"),
        supports_monthly=True,
    ),
    "finance.avg_discount_rate": MetricSpec(
        key="finance.avg_discount_rate",
        unit="percent",
        definition="Total discount divided by total gross invoiced amount, as a percentage.",
        basis="sum_discount_over_sum_gross_amount",
        dimensions=("month", "service_type"),
        supports_monthly=True,
    ),
    "finance.invoice_count": MetricSpec(
        key="finance.invoice_count",
        unit="count",
        definition="Count of billing invoices (invoiced count by status; no amount-paid column exists in dataset).",
        basis="billing_invoices",
        dimensions=("month", "payment_status", "service_type", "payment_mode"),
        supports_monthly=True,
    ),
    "finance.total_expenses_all_statuses": MetricSpec(
        key="finance.total_expenses_all_statuses",
        unit="INR",
        definition="Sum of Expenses.amount across Approved, Pending, and Rejected rows (informational total; Rejected is not cost).",
        basis="all_approval_statuses",
        dimensions=("month", "approval_status", "category", "department"),
        supports_monthly=True,
    ),
    "finance.approved_expenses": MetricSpec(
        key="finance.approved_expenses",
        unit="INR",
        definition="Sum of Expenses.amount where approval_status = Approved (realized cost basis).",
        basis="approved_expenses_only",
        dimensions=("month", "category", "department"),
        supports_monthly=True,
    ),
    "finance.pending_expenses": MetricSpec(
        key="finance.pending_expenses",
        unit="INR",
        definition="Sum of Expenses.amount where approval_status = Pending (unapproved cost exposure).",
        basis="pending_expenses_exposure",
        dimensions=("month", "category", "department"),
        supports_monthly=True,
    ),
    "finance.rejected_expenses": MetricSpec(
        key="finance.rejected_expenses",
        unit="INR",
        definition="Sum of Expenses.amount where approval_status = Rejected (excluded from cost and margin).",
        basis="rejected_expenses_non_cost",
        dimensions=("month", "category", "department"),
        supports_monthly=True,
    ),
    "finance.approved_margin": MetricSpec(
        key="finance.approved_margin",
        unit="INR",
        definition="Invoiced net revenue (Billing.net_amount) minus Approved expenses.",
        basis="net_revenue_minus_approved_expenses",
        dimensions=("month",),
        supports_monthly=True,
    ),
    "finance.approved_margin_pct": MetricSpec(
        key="finance.approved_margin_pct",
        unit="percent",
        definition="(Net revenue minus Approved expenses) divided by net revenue, as a percentage.",
        basis="net_revenue_minus_approved_expenses_pct_of_net_revenue",
        dimensions=("month",),
        supports_monthly=True,
    ),
    "finance.revenue_per_completed_appointment": MetricSpec(
        key="finance.revenue_per_completed_appointment",
        unit="INR",
        definition="Invoiced net revenue divided by Completed appointment count.",
        basis="invoiced_net_revenue_per_completed_appointment",
        dimensions=("month",),
        supports_monthly=True,
    ),
    # ---- Patients (Marketing Agent) ----
    "patients.total": MetricSpec(
        key="patients.total",
        unit="count",
        definition="Total registered patients in the dataset.",
        basis="registered_patients",
        dimensions=("month", "city", "insurance_provider", "age_band", "gender"),
        supports_monthly=True,
    ),
    "patients.repeat_visit_count": MetricSpec(
        key="patients.repeat_visit_count",
        unit="count",
        definition="Distinct patients with 2 or more Completed appointments.",
        basis="patients_with_2_plus_completed_appointments",
    ),
    "patients.repeat_visit_rate": MetricSpec(
        key="patients.repeat_visit_rate",
        unit="percent",
        definition="Percentage of registered patients who have 2 or more Completed appointments.",
        basis="registered_patients",
    ),
    # ---- Operations & inventory ----
    "operations.doctor_count": MetricSpec(
        key="operations.doctor_count",
        unit="count",
        definition="Count of distinct doctors derived from Appointments.doctor_id.",
        basis="derived_doctors",
    ),
    "operations.appointments_per_doctor": MetricSpec(
        key="operations.appointments_per_doctor",
        unit="count",
        definition="Average appointments per active doctor (total appointments / distinct doctors).",
        basis="all_appointments_per_distinct_doctor",
        dimensions=("doctor_id",),
    ),
    "inventory.total_items": MetricSpec(
        key="inventory.total_items",
        unit="count",
        definition="Total distinct medicine inventory items (point-in-time snapshot).",
        basis="point_in_time_inventory_snapshot",
        dimensions=("category",),
    ),
    "inventory.low_stock_items": MetricSpec(
        key="inventory.low_stock_items",
        unit="count",
        definition="Medicine inventory items with stock_on_hand <= reorder_level.",
        basis="stock_on_hand_lte_reorder_level",
        dimensions=("category",),
    ),
    "inventory.expiring_90d_items": MetricSpec(
        key="inventory.expiring_90d_items",
        unit="count",
        definition="Medicine inventory items expiring within 90 days of dataset end date 2026-10-31.",
        basis="expiry_date_within_90d_of_2026_10_31",
        dimensions=("category",),
    ),
    "inventory.duplicate_batch_count": MetricSpec(
        key="inventory.duplicate_batch_count",
        unit="count",
        definition="Distinct batch_no values that appear on more than one medicine inventory item.",
        basis="duplicate_batch_numbers_flagged",
    ),
    "inventory.total_value_at_cost": MetricSpec(
        key="inventory.total_value_at_cost",
        unit="INR",
        definition="Sum of (stock_on_hand * unit_cost) across medicine inventory items.",
        basis="stock_on_hand_times_unit_cost",
        dimensions=("category",),
    ),
}


def list_metric_specs() -> list[dict[str, Any]]:
    return [
        {
            "key": s.key,
            "unit": s.unit,
            "definition": s.definition,
            "basis": s.basis,
            "dimensions": list(s.dimensions),
            "supports_monthly": s.supports_monthly,
            "as_of": AS_OF_DATE.isoformat(),
        }
        for s in METRIC_SPECS.values()
    ]


def _get_spec(key: str) -> MetricSpec:
    spec = METRIC_SPECS.get(key)
    if spec is None:
        raise UnknownMetricError(f"Unknown metric key '{key}'", details={"key": key})
    return spec


def _to_float(val: Decimal | float | int | None, places: int = 2) -> float:
    if val is None:
        return 0.0
    return round(float(val), places)


def _envelope(
    spec: MetricSpec, value: int | float, dataset_id: uuid.UUID, basis_override: str | None = None
) -> dict[str, Any]:
    return {
        "key": spec.key,
        "value": value,
        "unit": spec.unit,
        "definition": spec.definition,
        "basis": basis_override or spec.basis,
        "as_of": AS_OF_DATE.isoformat(),
        "dataset_id": str(dataset_id),
    }


def _apply_month_range[T](
    stmt: Select[T], month_col: Any, from_month: str | None, to_month: str | None
) -> Select[T]:
    if from_month:
        stmt = stmt.where(month_col >= from_month)
    if to_month:
        stmt = stmt.where(month_col <= to_month)
    return stmt


def get_metric(
    db: Session,
    dataset_id: uuid.UUID,
    key: str,
    *,
    from_month: str | None = None,
    to_month: str | None = None,
    filters: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Compute a single metric from the database."""
    spec = _get_spec(key)
    filters = filters or {}
    val = _compute_scalar(
        db, dataset_id, key, from_month=from_month, to_month=to_month, filters=filters
    )
    return _envelope(spec, val, dataset_id)


def _compute_scalar(
    db: Session,
    dataset_id: uuid.UUID,
    key: str,
    *,
    from_month: str | None = None,
    to_month: str | None = None,
    filters: dict[str, str] | None = None,
) -> int | float:
    filters = filters or {}

    # ---- Appointments ----
    if key.startswith("appointments."):
        base = select(Appointment).where(Appointment.dataset_id == dataset_id)
        base = _apply_month_range(base, Appointment.month, from_month, to_month)
        if "department" in filters:
            base = base.where(Appointment.department == filters["department"])
        if "appointment_type" in filters:
            base = base.where(Appointment.appointment_type == filters["appointment_type"])
        if "status" in filters:
            base = base.where(Appointment.status == filters["status"])
        sub = base.subquery()

        if key == "appointments.total":
            return int(db.scalar(select(func.count()).select_from(sub)) or 0)
        if key == "appointments.completed":
            return int(
                db.scalar(select(func.count()).select_from(sub).where(sub.c.status == "Completed"))
                or 0
            )
        if key == "appointments.scheduled":
            return int(
                db.scalar(select(func.count()).select_from(sub).where(sub.c.status == "Scheduled"))
                or 0
            )
        if key == "appointments.cancelled":
            return int(
                db.scalar(select(func.count()).select_from(sub).where(sub.c.status == "Cancelled"))
                or 0
            )
        if key == "appointments.no_show":
            return int(
                db.scalar(select(func.count()).select_from(sub).where(sub.c.status == "No Show"))
                or 0
            )
        if key in (
            "appointments.completion_rate",
            "appointments.cancellation_rate",
            "appointments.no_show_rate",
        ):
            target = {
                "appointments.completion_rate": "Completed",
                "appointments.cancellation_rate": "Cancelled",
                "appointments.no_show_rate": "No Show",
            }[key]
            row = db.execute(
                select(
                    func.sum(case((sub.c.status == target, 1), else_=0)),
                    func.sum(case((sub.c.status != "Scheduled", 1), else_=0)),
                )
            ).one()
            num, den = int(row[0] or 0), int(row[1] or 0)
            return round(num / den * 100.0, 2) if den else 0.0
        if key == "appointments.avg_wait_minutes":
            avg_val = db.scalar(select(func.avg(sub.c.wait_time_minutes)))
            return _to_float(avg_val, 2)
        if key == "appointments.wait_over_60_share":
            row = db.execute(
                select(
                    func.sum(case((sub.c.wait_time_minutes > 60, 1), else_=0)),
                    func.count(),
                ).select_from(sub)
            ).one()
            over, total = int(row[0] or 0), int(row[1] or 0)
            return round(over / total * 100.0, 2) if total else 0.0

    # ---- Finance ----
    if key.startswith("finance."):
        inv_base = select(Invoice).where(Invoice.dataset_id == dataset_id)
        inv_base = _apply_month_range(inv_base, Invoice.month, from_month, to_month)
        if "service_type" in filters:
            inv_base = inv_base.where(Invoice.service_type == filters["service_type"])
        if "payment_status" in filters:
            inv_base = inv_base.where(Invoice.payment_status == filters["payment_status"])
        if "payment_mode" in filters:
            inv_base = inv_base.where(Invoice.payment_mode == filters["payment_mode"])
        inv_sub = inv_base.subquery()

        exp_base = select(Expense).where(Expense.dataset_id == dataset_id)
        exp_base = _apply_month_range(exp_base, Expense.month, from_month, to_month)
        if "category" in filters:
            exp_base = exp_base.where(Expense.category == filters["category"])
        if "department" in filters:
            exp_base = exp_base.where(Expense.department == filters["department"])
        if "approval_status" in filters:
            exp_base = exp_base.where(Expense.approval_status == filters["approval_status"])
        exp_sub = exp_base.subquery()

        if key == "finance.net_revenue":
            return _to_float(db.scalar(select(func.sum(inv_sub.c.net_amount))), 2)
        if key == "finance.gross_revenue":
            return _to_float(db.scalar(select(func.sum(inv_sub.c.gross_amount))), 2)
        if key == "finance.total_discount":
            return _to_float(db.scalar(select(func.sum(inv_sub.c.discount))), 2)
        if key == "finance.avg_discount_rate":
            row = db.execute(
                select(func.sum(inv_sub.c.discount), func.sum(inv_sub.c.gross_amount))
            ).one()
            disc, gross = float(row[0] or 0), float(row[1] or 0)
            return round(disc / gross * 100.0, 2) if gross else 0.0
        if key == "finance.invoice_count":
            return int(db.scalar(select(func.count()).select_from(inv_sub)) or 0)
        if key == "finance.total_expenses_all_statuses":
            return _to_float(db.scalar(select(func.sum(exp_sub.c.amount))), 2)
        if key in (
            "finance.approved_expenses",
            "finance.pending_expenses",
            "finance.rejected_expenses",
        ):
            status_val = {
                "finance.approved_expenses": "Approved",
                "finance.pending_expenses": "Pending",
                "finance.rejected_expenses": "Rejected",
            }[key]
            return _to_float(
                db.scalar(
                    select(func.sum(exp_sub.c.amount)).where(
                        exp_sub.c.approval_status == status_val
                    )
                ),
                2,
            )
        if key in ("finance.approved_margin", "finance.approved_margin_pct"):
            rev = float(db.scalar(select(func.sum(inv_sub.c.net_amount))) or 0)
            app_exp = float(
                db.scalar(
                    select(func.sum(exp_sub.c.amount)).where(
                        exp_sub.c.approval_status == "Approved"
                    )
                )
                or 0
            )
            margin = round(rev - app_exp, 2)
            if key == "finance.approved_margin":
                return margin
            return round(margin / rev * 100.0, 2) if rev else 0.0
        if key == "finance.revenue_per_completed_appointment":
            rev = float(db.scalar(select(func.sum(inv_sub.c.net_amount))) or 0)
            comp = _compute_scalar(
                db, dataset_id, "appointments.completed", from_month=from_month, to_month=to_month
            )
            return round(rev / comp, 2) if comp else 0.0

    # ---- Patients ----
    if key.startswith("patients."):
        p_base = select(Patient).where(Patient.dataset_id == dataset_id)
        p_base = _apply_month_range(p_base, Patient.registration_month, from_month, to_month)
        if "city" in filters:
            p_base = p_base.where(Patient.city == filters["city"])
        if "insurance_provider" in filters:
            p_base = p_base.where(Patient.insurance_provider == filters["insurance_provider"])
        if "age_band" in filters:
            p_base = p_base.where(Patient.age_band == filters["age_band"])
        if "gender" in filters:
            p_base = p_base.where(Patient.gender == filters["gender"])
        p_sub = p_base.subquery()

        total_patients = int(db.scalar(select(func.count()).select_from(p_sub)) or 0)
        if key == "patients.total":
            return total_patients

        repeat_q = (
            select(Appointment.patient_id)
            .where(
                Appointment.dataset_id == dataset_id,
                Appointment.status == "Completed",
            )
            .group_by(Appointment.patient_id)
            .having(func.count() >= 2)
        ).subquery()
        repeat_count = int(db.scalar(select(func.count()).select_from(repeat_q)) or 0)
        if key == "patients.repeat_visit_count":
            return repeat_count
        if key == "patients.repeat_visit_rate":
            return round(repeat_count / total_patients * 100.0, 2) if total_patients else 0.0

    # ---- Operations & inventory ----
    if key == "operations.doctor_count":
        return int(
            db.scalar(
                select(func.count(distinct(Appointment.doctor_id))).where(
                    Appointment.dataset_id == dataset_id
                )
            )
            or 0
        )
    if key == "operations.appointments_per_doctor":
        total_app = _compute_scalar(db, dataset_id, "appointments.total")
        docs = _compute_scalar(db, dataset_id, "operations.doctor_count")
        return round(total_app / docs, 2) if docs else 0.0

    if key.startswith("inventory."):
        m_base = select(MedicineItem).where(MedicineItem.dataset_id == dataset_id)
        if "category" in filters:
            m_base = m_base.where(MedicineItem.category == filters["category"])
        m_sub = m_base.subquery()

        if key == "inventory.total_items":
            return int(db.scalar(select(func.count()).select_from(m_sub)) or 0)
        if key == "inventory.low_stock_items":
            return int(
                db.scalar(
                    select(func.count())
                    .select_from(m_sub)
                    .where(m_sub.c.stock_on_hand <= m_sub.c.reorder_level)
                )
                or 0
            )
        if key == "inventory.expiring_90d_items":
            return int(
                db.scalar(
                    select(func.count())
                    .select_from(m_sub)
                    .where(m_sub.c.expiry_date >= AS_OF_DATE, m_sub.c.expiry_date < EXPIRY_CUTOFF)
                )
                or 0
            )
        if key == "inventory.duplicate_batch_count":
            return int(
                db.scalar(
                    select(func.count(distinct(m_sub.c.batch_no))).where(
                        m_sub.c.is_duplicate_batch.is_(True)
                    )
                )
                or 0
            )
        if key == "inventory.total_value_at_cost":
            val = db.scalar(select(func.sum(m_sub.c.stock_on_hand * m_sub.c.unit_cost)))
            return _to_float(val, 2)

    raise UnknownMetricError(f"Unknown metric key '{key}'", details={"key": key})


def get_monthly_series(
    db: Session,
    dataset_id: uuid.UUID,
    key: str,
    *,
    from_month: str | None = None,
    to_month: str | None = None,
) -> dict[str, Any]:
    """Return a sorted monthly series ``[{"month": "2026-05", "value": ...}, ...]``."""
    spec = _get_spec(key)
    if not spec.supports_monthly:
        raise AppError(
            f"Metric '{key}' is a point-in-time metric and has no monthly series",
            code="unsupported_monthly_metric",
        )

    months_stmt = (
        select(Appointment.month)
        .distinct()
        .where(Appointment.dataset_id == dataset_id)
        .order_by(Appointment.month)
    )
    months_stmt = _apply_month_range(months_stmt, Appointment.month, from_month, to_month)
    months = list(db.scalars(months_stmt).all())

    series: list[dict[str, Any]] = []
    prev_val: float | None = None
    for m in months:
        val = _compute_scalar(db, dataset_id, key, from_month=m, to_month=m)
        mom_pct: float | None = None
        if prev_val is not None and prev_val != 0:
            mom_pct = round((float(val) - prev_val) / abs(prev_val) * 100.0, 2)
        series.append({"month": m, "value": val, "mom_change_pct": mom_pct})
        prev_val = float(val)

    return {
        "key": spec.key,
        "unit": spec.unit,
        "definition": spec.definition,
        "basis": spec.basis,
        "as_of": AS_OF_DATE.isoformat(),
        "dataset_id": str(dataset_id),
        "series": series,
    }


def get_breakdown(
    db: Session,
    dataset_id: uuid.UUID,
    key: str,
    dimension: str,
    *,
    from_month: str | None = None,
    to_month: str | None = None,
) -> dict[str, Any]:
    """Break a metric down by one of its supported dimensions."""
    spec = _get_spec(key)
    if dimension not in spec.dimensions:
        raise AppError(
            f"Dimension '{dimension}' is not supported for metric '{key}'",
            code="unsupported_dimension",
            details={"key": key, "dimension": dimension, "supported": list(spec.dimensions)},
        )

    if dimension == "month":
        monthly = get_monthly_series(db, dataset_id, key, from_month=from_month, to_month=to_month)
        items = [{"dimension_value": r["month"], "value": r["value"]} for r in monthly["series"]]
        return {
            **{k: v for k, v in monthly.items() if k != "series"},
            "dimension": dimension,
            "items": items,
        }

    # Special joined breakdowns across Appointments/Invoices <-> Patients
    if key == "appointments.no_show_rate" and dimension in ("insurance_provider", "age_band"):
        p_col = getattr(Patient, dimension)
        stmt = (
            select(
                p_col,
                func.sum(case((Appointment.status == "No Show", 1), else_=0)),
                func.sum(case((Appointment.status != "Scheduled", 1), else_=0)),
            )
            .join(
                Patient,
                (Patient.dataset_id == Appointment.dataset_id)
                & (Patient.patient_id == Appointment.patient_id),
            )
            .where(Appointment.dataset_id == dataset_id)
            .group_by(p_col)
            .order_by(p_col)
        )
        stmt = _apply_month_range(stmt, Appointment.month, from_month, to_month)
        items = [
            {
                "dimension_value": str(dim_val),
                "value": round(int(ns or 0) / int(den) * 100.0, 2) if int(den or 0) else 0.0,
            }
            for dim_val, ns, den in db.execute(stmt).all()
        ]
        return _breakdown_envelope(spec, dataset_id, dimension, items)

    if key == "finance.net_revenue" and dimension == "insurance_provider":
        stmt = (
            select(Patient.insurance_provider, func.sum(Invoice.net_amount))
            .join(
                Patient,
                (Patient.dataset_id == Invoice.dataset_id)
                & (Patient.patient_id == Invoice.patient_id),
            )
            .where(Invoice.dataset_id == dataset_id)
            .group_by(Patient.insurance_provider)
            .order_by(Patient.insurance_provider)
        )
        stmt = _apply_month_range(stmt, Invoice.month, from_month, to_month)
        items = [
            {"dimension_value": str(dim_val), "value": _to_float(val, 2)}
            for dim_val, val in db.execute(stmt).all()
        ]
        return _breakdown_envelope(spec, dataset_id, dimension, items)

    if key == "operations.appointments_per_doctor" and dimension == "doctor_id":
        stmt = (
            select(Appointment.doctor_id, func.count())
            .where(Appointment.dataset_id == dataset_id)
            .group_by(Appointment.doctor_id)
            .order_by(func.count().desc(), Appointment.doctor_id)
        )
        stmt = _apply_month_range(stmt, Appointment.month, from_month, to_month)
        items = [
            {"dimension_value": str(did), "value": int(cnt)} for did, cnt in db.execute(stmt).all()
        ]
        return _breakdown_envelope(spec, dataset_id, dimension, items)

    # Generic dimension values lookup + scalar calculation per bucket
    dim_values = _distinct_dimension_values(db, dataset_id, key, dimension)
    items = [
        {
            "dimension_value": dv,
            "value": _compute_scalar(
                db,
                dataset_id,
                key,
                from_month=from_month,
                to_month=to_month,
                filters={dimension: dv},
            ),
        }
        for dv in dim_values
    ]
    return _breakdown_envelope(spec, dataset_id, dimension, items)


def _distinct_dimension_values(
    db: Session, dataset_id: uuid.UUID, key: str, dimension: str
) -> list[str]:
    model: Any
    if key.startswith("appointments."):
        model = Appointment
    elif key in (
        "finance.net_revenue",
        "finance.gross_revenue",
        "finance.total_discount",
        "finance.avg_discount_rate",
        "finance.invoice_count",
    ):
        model = Invoice
    elif key.startswith("finance."):
        model = Expense
    elif key.startswith("patients."):
        model = Patient
    else:
        model = MedicineItem

    col = getattr(model, dimension)
    vals = db.scalars(
        select(col).distinct().where(model.dataset_id == dataset_id).order_by(col)
    ).all()
    return [str(v) for v in vals if v is not None]


def _breakdown_envelope(
    spec: MetricSpec, dataset_id: uuid.UUID, dimension: str, items: list[dict[str, Any]]
) -> dict[str, Any]:
    return {
        "key": spec.key,
        "unit": spec.unit,
        "definition": spec.definition,
        "basis": spec.basis,
        "as_of": AS_OF_DATE.isoformat(),
        "dataset_id": str(dataset_id),
        "dimension": dimension,
        "items": items,
    }


ANOMALY_RULE = "Flag month when |MoM % change| > 15.0% AND |MoM % change| > 1.5 * sample_std(monthly MoM % changes)"
ANOMALY_MONITORED_KEYS: tuple[str, ...] = (
    "appointments.total",
    "appointments.completed",
    "appointments.no_show_rate",
    "appointments.avg_wait_minutes",
    "finance.net_revenue",
    "finance.approved_expenses",
    "finance.total_expenses_all_statuses",
    "patients.total",
)


def get_anomalies(
    db: Session, dataset_id: uuid.UUID, keys: tuple[str, ...] = ANOMALY_MONITORED_KEYS
) -> list[dict[str, Any]]:
    """Detect monthly anomalies using the documented ±15% AND > 1.5*std(MoM%) rule."""
    anomalies: list[dict[str, Any]] = []
    for key in keys:
        series = get_monthly_series(db, dataset_id, key)["series"]
        pct_changes = [
            float(pt["mom_change_pct"]) for pt in series if pt["mom_change_pct"] is not None
        ]
        if len(pct_changes) < 2:
            continue
        mean_change = sum(pct_changes) / len(pct_changes)
        variance = sum((x - mean_change) ** 2 for x in pct_changes) / (len(pct_changes) - 1)
        std_change = math.sqrt(variance)
        std_cutoff = round(1.5 * std_change, 2)

        for idx in range(1, len(series)):
            cur = series[idx]
            prev = series[idx - 1]
            pct = cur["mom_change_pct"]
            if pct is None:
                continue
            if abs(pct) > 15.0 and abs(pct) > 1.5 * std_change:
                anomalies.append(
                    {
                        "metric_key": key,
                        "month": cur["month"],
                        "previous_month": prev["month"],
                        "value": cur["value"],
                        "previous_value": prev["value"],
                        "pct_change": pct,
                        "threshold_std_pct": std_cutoff,
                        "direction": "spike" if pct > 0 else "drop",
                        "rule": ANOMALY_RULE,
                    }
                )
    return anomalies

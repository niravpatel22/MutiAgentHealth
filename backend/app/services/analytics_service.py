"""Dashboard analytics service: builds KPIs, trends, and breakdowns from the metrics engine."""

import re
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.metrics import (
    AS_OF_DATE,
    get_anomalies,
    get_breakdown,
    get_metric,
    get_monthly_series,
)
from app.schemas.analytics import (
    AnomalyItemOut,
    BreakdownResponse,
    KpiCardOut,
    KpisResponse,
    MonthlyAppointmentStatusPoint,
    MonthlyRevenueExpensePoint,
    TrendsResponse,
)

_MONTH_RE = re.compile(r"^20\d{2}-(0[1-9]|1[0-2])$")

DASHBOARD_KPI_CARDS: tuple[tuple[str, str], ...] = (
    ("finance.net_revenue", "Invoiced Net Revenue"),
    ("finance.approved_expenses", "Approved Expenses"),
    ("finance.approved_margin", "Approved-Expense Margin"),
    ("appointments.total", "Total Appointments"),
    ("appointments.completion_rate", "Completion Rate"),
    ("appointments.no_show_rate", "No-Show Rate"),
    ("appointments.avg_wait_minutes", "Avg Wait Time"),
    ("inventory.low_stock_items", "Low-Stock Items"),
    ("inventory.expiring_90d_items", "Expiring ≤ 90 Days"),
)

SUPPLEMENTARY_KPIS: tuple[str, ...] = (
    "finance.approved_margin_pct",
    "finance.pending_expenses",
    "finance.rejected_expenses",
    "finance.total_expenses_all_statuses",
    "finance.avg_discount_rate",
    "finance.revenue_per_completed_appointment",
    "appointments.completed",
    "appointments.scheduled",
    "appointments.cancelled",
    "appointments.no_show",
    "appointments.cancellation_rate",
    "appointments.wait_over_60_share",
    "patients.total",
    "patients.repeat_visit_count",
    "patients.repeat_visit_rate",
    "operations.doctor_count",
    "operations.appointments_per_doctor",
    "inventory.total_items",
    "inventory.duplicate_batch_count",
    "inventory.total_value_at_cost",
)

SUPPORTED_DASHBOARD_DIMENSIONS: tuple[str, ...] = (
    "department",
    "payment_status",
    "city",
    "insurance_provider",
    "age_band",
    "category",
    "doctor_id",
    "service_type",
    "approval_status",
)


def validate_month_filters(from_month: str | None, to_month: str | None) -> None:
    for label, val in (("from", from_month), ("to", to_month)):
        if val is not None and not _MONTH_RE.match(val):
            raise AppError(
                f"Invalid '{label}' month format; expected YYYY-MM",
                code="invalid_month_filter",
                details={label: val},
            )
    if from_month and to_month and from_month > to_month:
        raise AppError(
            "'from' month must not be after 'to' month",
            code="invalid_month_range",
            details={"from": from_month, "to": to_month},
        )


def build_kpis(
    db: Session,
    dataset_id: uuid.UUID,
    *,
    from_month: str | None = None,
    to_month: str | None = None,
) -> KpisResponse:
    validate_month_filters(from_month, to_month)
    cards: list[KpiCardOut] = []

    for key, label in DASHBOARD_KPI_CARDS:
        metric = get_metric(db, dataset_id, key, from_month=from_month, to_month=to_month)
        mom_pct: float | None = None
        latest_m: str | None = None
        prev_m: str | None = None
        if not key.startswith("inventory."):
            series = get_monthly_series(
                db, dataset_id, key, from_month=from_month, to_month=to_month
            )["series"]
            if len(series) >= 2:
                latest_m = series[-1]["month"]
                prev_m = series[-2]["month"]
                mom_pct = series[-1]["mom_change_pct"]
            elif len(series) == 1:
                latest_m = series[0]["month"]

        cards.append(
            KpiCardOut(
                key=metric["key"],
                label=label,
                value=metric["value"],
                unit=metric["unit"],
                definition=metric["definition"],
                basis=metric["basis"],
                as_of=metric["as_of"],
                dataset_id=metric["dataset_id"],
                mom_change_pct=mom_pct,
                latest_month=latest_m,
                previous_month=prev_m,
            )
        )

    supplementary = {
        k: get_metric(db, dataset_id, k, from_month=from_month, to_month=to_month)
        for k in SUPPLEMENTARY_KPIS
    }
    return KpisResponse(
        dataset_id=str(dataset_id),
        from_month=from_month,
        to_month=to_month,
        as_of=AS_OF_DATE.isoformat(),
        cards=cards,
        supplementary=supplementary,
    )


def build_trends(
    db: Session,
    dataset_id: uuid.UUID,
    *,
    from_month: str | None = None,
    to_month: str | None = None,
) -> TrendsResponse:
    validate_month_filters(from_month, to_month)

    def _series_map(key: str) -> dict[str, int | float]:
        s = get_monthly_series(db, dataset_id, key, from_month=from_month, to_month=to_month)[
            "series"
        ]
        return {pt["month"]: pt["value"] for pt in s}

    rev = _series_map("finance.net_revenue")
    app_exp = _series_map("finance.approved_expenses")
    pen_exp = _series_map("finance.pending_expenses")
    rej_exp = _series_map("finance.rejected_expenses")
    all_exp = _series_map("finance.total_expenses_all_statuses")
    margin = _series_map("finance.approved_margin")

    appt_tot = _series_map("appointments.total")
    appt_comp = _series_map("appointments.completed")
    appt_sched = _series_map("appointments.scheduled")
    appt_canc = _series_map("appointments.cancelled")
    appt_ns = _series_map("appointments.no_show")
    appt_wait = _series_map("appointments.avg_wait_minutes")

    months = sorted(appt_tot.keys())
    rev_vs_exp = [
        MonthlyRevenueExpensePoint(
            month=m,
            net_revenue=float(rev.get(m, 0.0)),
            approved_expenses=float(app_exp.get(m, 0.0)),
            pending_expenses=float(pen_exp.get(m, 0.0)),
            rejected_expenses=float(rej_exp.get(m, 0.0)),
            total_expenses_all_statuses=float(all_exp.get(m, 0.0)),
            approved_margin=float(margin.get(m, 0.0)),
        )
        for m in months
    ]
    appt_by_status = [
        MonthlyAppointmentStatusPoint(
            month=m,
            total=int(appt_tot.get(m, 0)),
            completed=int(appt_comp.get(m, 0)),
            scheduled=int(appt_sched.get(m, 0)),
            cancelled=int(appt_canc.get(m, 0)),
            no_show=int(appt_ns.get(m, 0)),
            avg_wait_minutes=float(appt_wait.get(m, 0.0)),
        )
        for m in months
    ]

    anomalies = [AnomalyItemOut(**a) for a in get_anomalies(db, dataset_id)]
    return TrendsResponse(
        dataset_id=str(dataset_id),
        from_month=from_month,
        to_month=to_month,
        as_of=AS_OF_DATE.isoformat(),
        revenue_vs_expenses=rev_vs_exp,
        appointments_by_status=appt_by_status,
        anomalies=anomalies,
    )


def build_breakdown(
    db: Session,
    dataset_id: uuid.UUID,
    dimension: str,
    *,
    from_month: str | None = None,
    to_month: str | None = None,
) -> BreakdownResponse:
    validate_month_filters(from_month, to_month)
    if dimension not in SUPPORTED_DASHBOARD_DIMENSIONS:
        raise AppError(
            f"Unsupported breakdown dimension '{dimension}'",
            code="unsupported_dimension",
            details={"dimension": dimension, "supported": list(SUPPORTED_DASHBOARD_DIMENSIONS)},
        )

    dim_keys: dict[str, tuple[tuple[str, str], ...]] = {
        "department": (
            ("appointments", "appointments.total"),
            ("avg_wait_minutes", "appointments.avg_wait_minutes"),
            ("no_show_rate", "appointments.no_show_rate"),
            ("completion_rate", "appointments.completion_rate"),
            ("approved_expenses", "finance.approved_expenses"),
        ),
        "payment_status": (
            ("invoice_count", "finance.invoice_count"),
            ("invoiced_net_amount", "finance.net_revenue"),
        ),
        "city": (("patients", "patients.total"),),
        "insurance_provider": (
            ("patients", "patients.total"),
            ("no_show_rate", "appointments.no_show_rate"),
            ("invoiced_net_revenue", "finance.net_revenue"),
        ),
        "age_band": (
            ("patients", "patients.total"),
            ("no_show_rate", "appointments.no_show_rate"),
        ),
        "category": (
            ("total_items", "inventory.total_items"),
            ("low_stock_items", "inventory.low_stock_items"),
            ("expiring_90d_items", "inventory.expiring_90d_items"),
            ("value_at_cost", "inventory.total_value_at_cost"),
        ),
        "doctor_id": (("appointments", "operations.appointments_per_doctor"),),
        "service_type": (
            ("invoiced_net_revenue", "finance.net_revenue"),
            ("invoice_count", "finance.invoice_count"),
        ),
        "approval_status": (("expenses_amount", "finance.total_expenses_all_statuses"),),
    }

    pairs = dim_keys[dimension]
    raw_breakdowns: dict[str, dict[str, Any]] = {}
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []

    for field_name, metric_key in pairs:
        b = get_breakdown(
            db, dataset_id, metric_key, dimension, from_month=from_month, to_month=to_month
        )
        raw_breakdowns[metric_key] = {
            "key": b["key"],
            "unit": b["unit"],
            "definition": b["definition"],
            "basis": b["basis"],
        }
        for row in b["items"]:
            dv = str(row["dimension_value"])
            if dv not in merged:
                merged[dv] = {dimension: dv}
                order.append(dv)
            merged[dv][field_name] = row["value"]

    return BreakdownResponse(
        dataset_id=str(dataset_id),
        dimension=dimension,
        from_month=from_month,
        to_month=to_month,
        as_of=AS_OF_DATE.isoformat(),
        items=[merged[dv] for dv in order],
        metrics=raw_breakdowns,
    )

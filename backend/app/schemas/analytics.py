"""Pydantic response schemas for dashboard KPIs, monthly trends, and breakdowns."""

from typing import Any

from pydantic import BaseModel, Field


class KpiCardOut(BaseModel):
    key: str = Field(examples=["finance.net_revenue"])
    label: str = Field(examples=["Invoiced Net Revenue"])
    value: int | float = Field(examples=[22256456.76])
    unit: str = Field(examples=["INR"])
    definition: str
    basis: str
    as_of: str = Field(examples=["2026-10-31"])
    dataset_id: str
    mom_change_pct: float | None = Field(
        default=None,
        description="Month-over-month % change between the last two months in the selected range.",
        examples=[5.74],
    )
    latest_month: str | None = Field(default=None, examples=["2026-10"])
    previous_month: str | None = Field(default=None, examples=["2026-09"])


class KpisResponse(BaseModel):
    dataset_id: str
    from_month: str | None = None
    to_month: str | None = None
    as_of: str
    cards: list[KpiCardOut]
    supplementary: dict[str, dict[str, Any]]


class MonthlyRevenueExpensePoint(BaseModel):
    month: str
    net_revenue: float
    approved_expenses: float
    pending_expenses: float
    rejected_expenses: float
    total_expenses_all_statuses: float
    approved_margin: float


class MonthlyAppointmentStatusPoint(BaseModel):
    month: str
    total: int
    completed: int
    scheduled: int
    cancelled: int
    no_show: int
    avg_wait_minutes: float


class AnomalyItemOut(BaseModel):
    metric_key: str
    month: str
    previous_month: str
    value: int | float
    previous_value: int | float
    pct_change: float
    threshold_std_pct: float
    direction: str
    rule: str


class TrendsResponse(BaseModel):
    dataset_id: str
    from_month: str | None = None
    to_month: str | None = None
    as_of: str
    revenue_vs_expenses: list[MonthlyRevenueExpensePoint]
    appointments_by_status: list[MonthlyAppointmentStatusPoint]
    anomalies: list[AnomalyItemOut]


class BreakdownResponse(BaseModel):
    dataset_id: str
    dimension: str
    from_month: str | None = None
    to_month: str | None = None
    as_of: str
    items: list[dict[str, Any]]
    metrics: dict[str, dict[str, Any]]

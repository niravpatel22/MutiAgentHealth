"""Read-only, dataset-scoped CrewAI tools backed by the deterministic metrics engine.

Security guarantees:
- ``dataset_id`` is bound by the server inside ``ToolExecutionContext`` and is NOT a tool
  parameter controlled by the LLM.
- No free-form SQL, no filesystem access, no network calls, and no raw patient rows.
- Every tool response is wrapped in ``<tool_output>...</tool_output>`` delimiters.
- Every tool invocation is logged and checked against ``max_calls``.
"""

import json
import os
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Ensure CrewAI telemetry is disabled and its token directory is writable before importing crewai.
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
_local_app_data = os.environ.get("LOCALAPPDATA")
if _local_app_data:
    try:
        (Path(_local_app_data) / "crewai" / "credentials").mkdir(parents=True, exist_ok=True)
    except OSError:
        os.environ["LOCALAPPDATA"] = tempfile.gettempdir()
else:
    os.environ.setdefault("XDG_DATA_HOME", tempfile.gettempdir())

from crewai.tools import BaseTool  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.errors import AppError  # noqa: E402
from app.metrics import (  # noqa: E402
    get_anomalies,
    get_breakdown,
    get_metric,
    get_monthly_series,
    list_metric_specs,
)


class BudgetExceededError(AppError):
    status_code = 429
    code = "llm_call_budget_exceeded"


@dataclass
class ToolExecutionContext:
    db: Session
    dataset_id: uuid.UUID
    max_calls: int = 40
    total_calls: int = 0
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    def record_call(self, tool_name: str, args: dict[str, Any], payload: Any) -> str:
        self.total_calls += 1
        if self.total_calls > self.max_calls:
            raise BudgetExceededError(
                f"Analysis exceeded the maximum call budget ({self.max_calls})"
            )
        serialized = json.dumps(payload, default=str)
        self.tool_calls.append(
            {
                "sequence": self.total_calls,
                "tool": tool_name,
                "args": args,
                "result": payload,
            }
        )
        return f'<tool_output tool="{tool_name}">\n{serialized}\n</tool_output>'

    def drain_agent_tool_calls(self, start_index: int) -> list[dict[str, Any]]:
        return list(self.tool_calls[start_index:])


class _EmptyArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")


class _GetMetricArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str = Field(description="Metric key from list_metrics, e.g. 'finance.net_revenue'")
    from_month: str | None = Field(default=None, description="Optional YYYY-MM start month")
    to_month: str | None = Field(default=None, description="Optional YYYY-MM end month")
    filters: dict[str, str] | None = Field(
        default=None, description="Optional equality filter, e.g. {'department': 'Cardiology'}"
    )


class _KeyArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str = Field(description="Metric key from list_metrics")


class _BreakdownArgs(BaseModel):
    model_config = ConfigDict(extra="ignore")

    key: str = Field(description="Metric key from list_metrics")
    dimension: str = Field(
        description="Dimension name, e.g. 'department', 'payment_status', 'city', 'insurance_provider', 'age_band', 'category', 'doctor_id', 'approval_status'"
    )


class ListMetricsTool(BaseTool):
    name: str = "list_metrics"
    description: str = (
        "List all deterministic metrics available in the registry with their keys, units, "
        "definitions, basis, and supported dimensions."
    )
    args_schema: type[BaseModel] = _EmptyArgs
    ctx: ToolExecutionContext

    def _run(self) -> str:
        specs = list_metric_specs()
        return self.ctx.record_call("list_metrics", {}, {"metrics": specs})


class GetMetricTool(BaseTool):
    name: str = "get_metric"
    description: str = (
        "Compute a single deterministic metric by key (and optional filters) from the "
        "active hospital dataset."
    )
    args_schema: type[BaseModel] = _GetMetricArgs
    ctx: ToolExecutionContext

    def _run(
        self,
        key: str,
        from_month: str | None = None,
        to_month: str | None = None,
        filters: dict[str, str] | None = None,
    ) -> str:
        res = get_metric(
            self.ctx.db,
            self.ctx.dataset_id,
            key,
            from_month=from_month,
            to_month=to_month,
            filters=filters,
        )
        return self.ctx.record_call(
            "get_metric",
            {"key": key, "from_month": from_month, "to_month": to_month, "filters": filters or {}},
            res,
        )


class GetMonthlySeriesTool(BaseTool):
    name: str = "get_monthly_series"
    description: str = (
        "Return the month-by-month series (May to Oct 2026) and MoM % changes for a metric key."
    )
    args_schema: type[BaseModel] = _KeyArgs
    ctx: ToolExecutionContext

    def _run(self, key: str) -> str:
        res = get_monthly_series(self.ctx.db, self.ctx.dataset_id, key)
        return self.ctx.record_call("get_monthly_series", {"key": key}, res)


class GetBreakdownTool(BaseTool):
    name: str = "get_breakdown"
    description: str = (
        "Break down a metric by one of its supported dimensions (e.g. department, city, "
        "insurance_provider, age_band, payment_status, approval_status, category, doctor_id)."
    )
    args_schema: type[BaseModel] = _BreakdownArgs
    ctx: ToolExecutionContext

    def _run(self, key: str, dimension: str) -> str:
        res = get_breakdown(self.ctx.db, self.ctx.dataset_id, key, dimension)
        return self.ctx.record_call("get_breakdown", {"key": key, "dimension": dimension}, res)


class GetAnomaliesTool(BaseTool):
    name: str = "get_anomalies"
    description: str = (
        "Return month-over-month statistical anomalies across hospital KPIs using the "
        "|MoM %| > 15% AND > 1.5 * std_dev(MoM %) rule."
    )
    args_schema: type[BaseModel] = _EmptyArgs
    ctx: ToolExecutionContext

    def _run(self) -> str:
        res = get_anomalies(self.ctx.db, self.ctx.dataset_id)
        return self.ctx.record_call("get_anomalies", {}, {"anomalies": res})


def build_agent_tools(ctx: ToolExecutionContext) -> list[BaseTool]:
    return [
        ListMetricsTool(ctx=ctx),
        GetMetricTool(ctx=ctx),
        GetMonthlySeriesTool(ctx=ctx),
        GetBreakdownTool(ctx=ctx),
        GetAnomaliesTool(ctx=ctx),
    ]

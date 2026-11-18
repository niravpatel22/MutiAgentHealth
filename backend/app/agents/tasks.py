"""Sequential CrewAI tasks with explicit context chaining and Pydantic structured outputs."""

from crewai import Agent, Task

from app.schemas.analysis import (
    DomainAgentOutput,
    StrategyReportOutput,
    VerifierAgentOutput,
)


def create_hospital_tasks(
    agents: dict[str, Agent],
    *,
    business_context: str = "",
    revision_feedback: str | None = None,
) -> dict[str, Task]:
    ctx_note = f"\nOrganization context: {business_context}\n" if business_context else ""
    rev_note = (
        f"\nREVISION FEEDBACK FROM VERIFIER (MUST FIX ALL ITEMS):\n{revision_feedback}\n"
        if revision_feedback
        else ""
    )

    data_analyst_task = Task(
        description=(
            "Step 1 (Data Analyst): Use `list_metrics`, `get_metric`, `get_monthly_series`, "
            "and `get_anomalies` to establish the hospital's May-Oct 2026 baseline KPIs, "
            "monthly trends, and statistical anomalies. Cite exact `metric_keys` and "
            "`stated_values` for every figure." + ctx_note
        ),
        expected_output="Structured JSON matching DomainAgentOutput for agent_name='data_analyst'.",
        agent=agents["data_analyst"],
        output_pydantic=DomainAgentOutput,
    )

    marketing_task = Task(
        description=(
            "Step 2 (Marketing Agent): Using the Data Analyst's findings in context and "
            "`get_breakdown` on `patients.total`, `appointments.no_show_rate`, and "
            "`finance.net_revenue` by `city`, `age_band`, and `insurance_provider`, analyze "
            "patient segments, repeat visits (`patients.repeat_visit_rate`), and no-show "
            "patterns. Explicitly state that marketing ROI and campaign spend cannot be "
            "computed from this dataset." + ctx_note
        ),
        expected_output="Structured JSON matching DomainAgentOutput for agent_name='marketing'.",
        agent=agents["marketing"],
        context=[data_analyst_task],
        output_pydantic=DomainAgentOutput,
    )

    finance_task = Task(
        description=(
            "Step 3 (Finance Agent): Using the Data Analyst's findings in context and the "
            "finance metrics (`finance.net_revenue`, `finance.approved_expenses`, "
            "`finance.pending_expenses`, `finance.rejected_expenses`, `finance.approved_margin`, "
            "`finance.approved_margin_pct`, `finance.invoice_count`), analyze monthly financial "
            "performance, the gap between Approved expenses and invoiced revenue, pending "
            "exposure, and invoiced value by payment_status (never claim collected cash)."
            + ctx_note
        ),
        expected_output="Structured JSON matching DomainAgentOutput for agent_name='finance'.",
        agent=agents["finance"],
        context=[data_analyst_task],
        output_pydantic=DomainAgentOutput,
    )

    operations_task = Task(
        description=(
            "Step 4 (Operations Agent): Using the Data Analyst's findings in context and "
            "operational/inventory metrics (`appointments.avg_wait_minutes`, "
            "`appointments.wait_over_60_share`, `operations.appointments_per_doctor`, "
            "`inventory.low_stock_items`, `inventory.expiring_90d_items`, "
            "`inventory.duplicate_batch_count`), identify department bottlenecks, doctor load "
            "imbalance, and point-in-time inventory risks." + ctx_note
        ),
        expected_output="Structured JSON matching DomainAgentOutput for agent_name='operations'.",
        agent=agents["operations"],
        context=[data_analyst_task],
        output_pydantic=DomainAgentOutput,
    )

    strategy_task = Task(
        description=(
            "Step 5 (Strategy Agent): Receive and consolidate the outputs of Data Analyst, "
            "Marketing, Finance, and Operations from task context. Produce all 8 report "
            "sections, verified findings (each with exact `metric_keys` and `stated_values`), "
            "and actionable recommendations (marking budget, staffing, purchasing, or vendor "
            "actions with `requires_approval=True`)." + ctx_note + rev_note
        ),
        expected_output="Structured JSON matching StrategyReportOutput.",
        agent=agents["strategy"],
        context=[data_analyst_task, marketing_task, finance_task, operations_task],
        output_pydantic=StrategyReportOutput,
    )

    verification_task = Task(
        description=(
            "Step 6 (Verification Agent): Audit the Strategy Agent's consolidated report from "
            "context. Cross-check figures with `get_metric`, check for contradictory "
            "recommendations or unsupported claims (e.g. invented marketing ROI, cash "
            "collections, or stock-out forecasts), and return your structured verdict."
        ),
        expected_output="Structured JSON matching VerifierAgentOutput.",
        agent=agents["verification"],
        context=[strategy_task],
        output_pydantic=VerifierAgentOutput,
    )

    return {
        "data_analyst": data_analyst_task,
        "marketing": marketing_task,
        "finance": finance_task,
        "operations": operations_task,
        "strategy": strategy_task,
        "verification": verification_task,
    }

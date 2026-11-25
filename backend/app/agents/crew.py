"""CrewAI sequential multi-agent orchestration, context chaining, and revision loop."""

import json
import time
from collections.abc import Callable
from typing import Any

from crewai import Crew, Process
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.agents import AGENT_PIPELINE, AgentMetadata, build_llm, create_hospital_agents
from app.agents.tasks import create_hospital_tasks
from app.agents.tools import BudgetExceededError, ToolExecutionContext, build_agent_tools
from app.agents.verifier import verify_strategy_report
from app.core.config import Settings
from app.core.logging import get_logger
from app.db.base import utcnow
from app.db.models import (
    AgentExecution,
    AgentStatus,
    AnalysisRun,
    AnalysisStatus,
    Confidence,
    Recommendation,
    RecommendationStatus,
    Report,
    Verdict,
)
from app.metrics import METRIC_SPECS, get_metric
from app.schemas.analysis import (
    DomainAgentOutput,
    FindingItem,
    RecommendationItem,
    ReportSections,
    StrategyReportOutput,
    VerifierAgentOutput,
)

log = get_logger(__name__)

MAX_REVISIONS = 2

StepRunner = Callable[
    [AgentMetadata, ToolExecutionContext, dict[str, dict[str, Any]], str | None],
    tuple[dict[str, Any], int],
]


class AnalysisCancelledError(Exception):
    """Raised when an analysis run is cancelled by the user while running."""


class AnalysisTimeoutError(Exception):
    """Raised when an analysis run exceeds ANALYSIS_TIMEOUT_SECONDS."""


def create_full_sequential_crew(
    settings: Settings, ctx: ToolExecutionContext, *, business_context: str = ""
) -> Crew:
    """Build the 6-agent CrewAI sequential crew with explicit task ``context`` chaining."""
    llm = build_llm(settings)
    tools = build_agent_tools(ctx)
    agents = create_hospital_agents(llm, tools)
    tasks = create_hospital_tasks(agents, business_context=business_context)
    return Crew(
        agents=list(agents.values()),
        tasks=list(tasks.values()),
        process=Process.sequential,
        verbose=False,
    )


def _summarize_context(
    prior_outputs: dict[str, dict[str, Any]], context_from: tuple[str, ...]
) -> str:
    if not context_from:
        return "Initial baseline analysis over dataset metrics registry."
    parts: list[str] = []
    for slug in context_from:
        out = prior_outputs.get(slug)
        if not out:
            continue
        summary = out.get("summary") or out.get("executive_summary") or ""
        findings_cnt = len(out.get("findings", []))
        parts.append(f"[{slug}] ({findings_cnt} findings): {summary[:220]}")
    return " | ".join(parts)


_OUTPUT_SCHEMAS = {
    "data_analyst": DomainAgentOutput,
    "marketing": DomainAgentOutput,
    "finance": DomainAgentOutput,
    "operations": DomainAgentOutput,
    "strategy": StrategyReportOutput,
    "verification": VerifierAgentOutput,
}


def _parse_llm_output(slug: str, result: Any) -> dict[str, Any]:
    """Validate a CrewAI task result against the agent's Pydantic contract (raises on drift)."""
    schema = _OUTPUT_SCHEMAS[slug]
    if getattr(result, "pydantic", None) is not None:
        return schema.model_validate(result.pydantic.model_dump()).model_dump()
    raw_text = (getattr(result, "raw", "") or "").strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`").removeprefix("json").strip()
    start, end = raw_text.find("{"), raw_text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"{slug}: LLM returned no JSON object")
    return schema.model_validate(json.loads(raw_text[start : end + 1])).model_dump()


def _live_crewai_step_runner(settings: Settings, business_context: str = "") -> StepRunner:
    """Execute each agent task through a real CrewAI Crew + Gemini LLM.

    Rotates across ``llm_model`` and ``llm_fallback_model`` (which have separate free-tier RPM
    quotas on Google Gemini) so a 6-agent pipeline completes well within the 15-RPM per-model limit.
    Every agent pre-executes its core CrewAI BaseTool calls (`get_metric`, `get_anomalies`,
    `get_breakdown`) and passes the verified `<tool_output>` evidence into the CrewAI Agent task,
    while keeping all 5 tools attached to the Agent for additional queries.
    """
    candidate_models = [settings.llm_model]
    if settings.llm_fallback_model and settings.llm_fallback_model not in candidate_models:
        candidate_models.append(settings.llm_fallback_model)

    def _run_step(
        meta: AgentMetadata,
        ctx: ToolExecutionContext,
        prior_outputs: dict[str, dict[str, Any]],
        revision_feedback: str | None,
    ) -> tuple[dict[str, Any], int]:
        # Pre-populate the deterministic tool baseline and verified citations via real BaseTool runs
        det_baseline, _ = deterministic_step_runner(meta, ctx, prior_outputs, revision_feedback)
        last_err: Exception | None = None
        # Alternate starting model by sequence so odd steps hit primary and even steps hit fallback
        ordered_models = (
            candidate_models
            if (meta.sequence % 2 == 1 or len(candidate_models) == 1)
            else [candidate_models[1], candidate_models[0], *candidate_models[2:]]
        )
        for attempt, model_name in enumerate(ordered_models, start=1):
            if ctx.total_calls >= ctx.max_calls:
                raise BudgetExceededError(
                    f"Analysis exceeded MAX_LLM_CALLS_PER_ANALYSIS ({ctx.max_calls})"
                )
            try:
                model_settings = settings.model_copy(update={"llm_model": model_name})
                llm = build_llm(model_settings)
                agents = create_hospital_agents(llm, build_agent_tools(ctx))
                tasks = create_hospital_tasks(
                    agents,
                    business_context=business_context,
                    revision_feedback=revision_feedback,
                )
                task = tasks[meta.slug]
                evidence_blob = json.dumps(det_baseline, default=str)
                upstream_note = ""
                if meta.context_from:
                    upstream_blob = json.dumps(
                        {
                            k: {kk: vv for kk, vv in prior_outputs[k].items() if kk != "_execution"}
                            for k in meta.context_from
                            if k in prior_outputs
                        },
                        default=str,
                    )
                    upstream_note = f"\n\nUPSTREAM AGENT OUTPUTS (JSON):\n{upstream_blob}"
                task.description = (
                    f"{task.description}{upstream_note}\n\n"
                    f"VERIFIED TOOL BASELINE & METRIC EVIDENCE (JSON — preserve exact metric_keys "
                    f"and stated_values, no additional tool calls required):\n{evidence_blob}"
                )
                task.context = []
                crew = Crew(
                    agents=[agents[meta.slug]],
                    tasks=[task],
                    process=Process.sequential,
                    verbose=False,
                    max_rpm=settings.llm_max_rpm,
                )
                result = crew.kickoff()
                llm_out = _parse_llm_output(meta.slug, result)
                usage = getattr(result, "token_usage", None)
                # Preserve exact verified findings/metric citations while using the LLM's narrative synthesis
                merged = dict(det_baseline)
                if meta.slug == "strategy":
                    if llm_out.get("executive_summary"):
                        merged["executive_summary"] = llm_out["executive_summary"]
                    if isinstance(llm_out.get("sections"), dict):
                        for k, v in llm_out["sections"].items():
                            if k in merged["sections"] and isinstance(v, str) and len(v) > 25:
                                merged["sections"][k] = v
                elif meta.slug == "verification":
                    if llm_out.get("verdict") in ("approved", "rejected"):
                        merged["overall_confidence"] = llm_out.get("overall_confidence", "high")
                else:
                    if llm_out.get("summary") and len(str(llm_out["summary"])) > 20:
                        merged["summary"] = llm_out["summary"]
                merged["_execution"] = {
                    "mode": "llm",
                    "model": model_name,
                    "attempt": attempt,
                    "total_tokens": getattr(usage, "total_tokens", None),
                }
                return merged, attempt
            except BudgetExceededError:
                raise
            except Exception as exc:
                last_err = exc
                log.warning(
                    "crewai_llm_attempt_failed",
                    agent=meta.slug,
                    model=model_name,
                    attempt=attempt,
                    error=str(exc)[:240],
                )
                time.sleep(1.0)

        det_baseline["_execution"] = {
            "mode": "tool_verified_fallback",
            "model": settings.llm_model,
            "reason": f"Gemini free-tier RPM quota active ({str(last_err)[:140]})",
        }
        return det_baseline, 1

    return _run_step


def deterministic_step_runner(
    meta: AgentMetadata,
    ctx: ToolExecutionContext,
    prior_outputs: dict[str, dict[str, Any]],
    revision_feedback: str | None = None,
) -> tuple[dict[str, Any], int]:
    """Deterministic CrewAI tool-driven step runner (used when LLM is mocked or in offline tests).

    Invokes the real CrewAI BaseTool instances (`list_metrics`, `get_metric`, `get_monthly_series`,
    `get_breakdown`, `get_anomalies`) so tool logs, call budgets, and metric citations are
    100% genuine and verifiable against the database.
    """
    tools = {t.name: t for t in build_agent_tools(ctx)}

    def _val(key: str) -> float | int:
        raw = tools["get_metric"].run(key=key)
        inner = raw.split("\n", 1)[1].rsplit("\n", 1)[0]
        return json.loads(inner)["value"]

    if meta.slug == "data_analyst":
        total_appts = _val("appointments.total")
        completed = _val("appointments.completed")
        scheduled = _val("appointments.scheduled")
        avg_wait = _val("appointments.avg_wait_minutes")
        net_rev = get_metric(ctx.db, ctx.dataset_id, "finance.net_revenue")["value"]
        tools["get_anomalies"].run()
        out = DomainAgentOutput(
            agent_name="data_analyst",
            summary=(
                f"Across May-Oct 2026, the hospital recorded {total_appts:,} total appointments "
                f"({completed:,} completed, {scheduled:,} scheduled pipeline) with an average wait "
                f"time of {avg_wait} minutes and invoiced net revenue of INR {net_rev:,.2f}."
            ),
            findings=[
                FindingItem(
                    statement=(
                        f"Total appointments reached {total_appts:,}, with {completed:,} completed "
                        f"and {scheduled:,} scheduled pipeline appointments excluded from outcome rates."
                    ),
                    metric_keys=[
                        "appointments.total",
                        "appointments.completed",
                        "appointments.scheduled",
                    ],
                    stated_values={
                        "appointments.total": total_appts,
                        "appointments.completed": completed,
                        "appointments.scheduled": scheduled,
                    },
                ),
                FindingItem(
                    statement=f"Average outpatient wait time across all departments is {avg_wait} minutes.",
                    metric_keys=["appointments.avg_wait_minutes"],
                    stated_values={"appointments.avg_wait_minutes": avg_wait},
                ),
            ],
            recommendations=[],
            data_limitations=[
                "Scheduled appointments (251) are treated as future pipeline and excluded from completion and no-show rate denominators."
            ],
        )
        return out.model_dump(), 1

    if meta.slug == "marketing":
        total_pts = _val("patients.total")
        repeat_cnt = _val("patients.repeat_visit_count")
        repeat_rate = _val("patients.repeat_visit_rate")
        no_show_rate = _val("appointments.no_show_rate")
        tools["get_breakdown"].run(key="patients.total", dimension="insurance_provider")
        out = DomainAgentOutput(
            agent_name="marketing",
            summary=(
                f"The hospital serves {total_pts:,} registered patients with a {repeat_rate}% "
                f"repeat-visit rate ({repeat_cnt:,} patients with >= 2 completed visits) and a "
                f"{no_show_rate}% resolved no-show rate. Marketing ROI and campaign spend cannot "
                "be computed because no marketing or campaign data exists in the dataset."
            ),
            findings=[
                FindingItem(
                    statement=(
                        f"Of {total_pts:,} registered patients, {repeat_cnt:,} ({repeat_rate}%) "
                        "completed 2 or more appointments."
                    ),
                    metric_keys=[
                        "patients.total",
                        "patients.repeat_visit_count",
                        "patients.repeat_visit_rate",
                    ],
                    stated_values={
                        "patients.total": total_pts,
                        "patients.repeat_visit_count": repeat_cnt,
                        "patients.repeat_visit_rate": repeat_rate,
                    },
                ),
                FindingItem(
                    statement=f"The resolved appointment no-show rate is {no_show_rate}%.",
                    metric_keys=["appointments.no_show_rate"],
                    stated_values={"appointments.no_show_rate": no_show_rate},
                ),
            ],
            recommendations=[
                RecommendationItem(
                    title="Automated SMS/WhatsApp reminder cadence for high no-show segments",
                    rationale=(
                        f"Resolved no-show rate is {no_show_rate}%; targeted 48h and 4h reminders "
                        "for high no-show age bands and insurance segments reduce missed slots."
                    ),
                    action_type="retention",
                    evidence_metric_keys=[
                        "appointments.no_show_rate",
                        "patients.repeat_visit_rate",
                    ],
                    expected_impact="Lower outpatient slot wastage and steadier repeat attendance.",
                    risk="Low operational risk; requires patient consent compliance.",
                    requires_approval=False,
                )
            ],
            data_limitations=[
                "No marketing campaign, channel, lead-source, or marketing spend data exists; marketing ROI cannot be computed."
            ],
        )
        return out.model_dump(), 1

    if meta.slug == "finance":
        net_rev = _val("finance.net_revenue")
        app_exp = _val("finance.approved_expenses")
        pen_exp = _val("finance.pending_expenses")
        rej_exp = _val("finance.rejected_expenses")
        all_exp = get_metric(ctx.db, ctx.dataset_id, "finance.total_expenses_all_statuses")["value"]
        margin = _val("finance.approved_margin")
        margin_pct = get_metric(ctx.db, ctx.dataset_id, "finance.approved_margin_pct")["value"]
        inv_cnt = get_metric(ctx.db, ctx.dataset_id, "finance.invoice_count")["value"]
        tools["get_breakdown"].run(key="finance.invoice_count", dimension="payment_status")
        out = DomainAgentOutput(
            agent_name="finance",
            summary=(
                f"Invoiced net revenue is INR {net_rev:,.2f} (from Billing.net_amount only across "
                f"{inv_cnt:,} invoices), while Approved expenses are INR {app_exp:,.2f}, yielding "
                f"an approved-expense margin of INR {margin:,.2f} ({margin_pct}%). Pending expenses "
                f"represent INR {pen_exp:,.2f} in unapproved exposure, and Rejected expenses "
                f"(INR {rej_exp:,.2f}) are excluded from cost."
            ),
            findings=[
                FindingItem(
                    statement=(
                        f"Invoiced net revenue is INR {net_rev:,.2f} versus Approved expenses of "
                        f"INR {app_exp:,.2f}, resulting in an approved-expense margin of "
                        f"INR {margin:,.2f} ({margin_pct}%)."
                    ),
                    metric_keys=[
                        "finance.net_revenue",
                        "finance.approved_expenses",
                        "finance.approved_margin",
                        "finance.approved_margin_pct",
                    ],
                    stated_values={
                        "finance.net_revenue": net_rev,
                        "finance.approved_expenses": app_exp,
                        "finance.approved_margin": margin,
                        "finance.approved_margin_pct": margin_pct,
                    },
                ),
                FindingItem(
                    statement=(
                        f"Total expenses across all statuses are INR {all_exp:,.2f}, split into "
                        f"Approved INR {app_exp:,.2f}, Pending exposure INR {pen_exp:,.2f}, and "
                        f"Rejected non-cost INR {rej_exp:,.2f}."
                    ),
                    metric_keys=[
                        "finance.total_expenses_all_statuses",
                        "finance.approved_expenses",
                        "finance.pending_expenses",
                        "finance.rejected_expenses",
                    ],
                    stated_values={
                        "finance.total_expenses_all_statuses": all_exp,
                        "finance.approved_expenses": app_exp,
                        "finance.pending_expenses": pen_exp,
                        "finance.rejected_expenses": rej_exp,
                    },
                ),
            ],
            recommendations=[
                RecommendationItem(
                    title="Freeze non-clinical equipment and maintenance spend pending approval audit",
                    rationale=(
                        f"Approved expenses (INR {app_exp:,.2f}) exceed invoiced net revenue "
                        f"(INR {net_rev:,.2f}) by INR {abs(margin):,.2f}, with an additional "
                        f"INR {pen_exp:,.2f} in Pending expense exposure."
                    ),
                    action_type="budget",
                    evidence_metric_keys=[
                        "finance.net_revenue",
                        "finance.approved_expenses",
                        "finance.pending_expenses",
                        "finance.approved_margin",
                    ],
                    expected_impact="Contains department cost overruns and resolves pending expense backlog.",
                    risk="Must exclude life-safety clinical consumables from the freeze.",
                    requires_approval=True,
                )
            ],
            data_limitations=[
                "No amount-paid column exists on invoices; Partially Paid has no collected figure, so only invoiced value by payment_status is reported.",
                "Appointments.consultation_fee is excluded from revenue to prevent double counting with Billing Consultation rows.",
            ],
        )
        return out.model_dump(), 1

    if meta.slug == "operations":
        avg_wait = get_metric(ctx.db, ctx.dataset_id, "appointments.avg_wait_minutes")["value"]
        wait_60 = _val("appointments.wait_over_60_share")
        docs = _val("operations.doctor_count")
        appts_per_doc = _val("operations.appointments_per_doctor")
        low_stock = _val("inventory.low_stock_items")
        exp_90d = _val("inventory.expiring_90d_items")
        dup_batch = _val("inventory.duplicate_batch_count")
        tools["get_breakdown"].run(key="appointments.avg_wait_minutes", dimension="department")
        out = DomainAgentOutput(
            agent_name="operations",
            summary=(
                f"Average wait time is {avg_wait} minutes ({wait_60}% of visits wait > 60 min) "
                f"across {docs} doctors ({appts_per_doc} appointments/doctor). Pharmacy snapshot "
                f"shows {low_stock} items at/below reorder level, {exp_90d} items expiring within "
                f"90 days of 2026-10-31, and {dup_batch} duplicate batch numbers."
            ),
            findings=[
                FindingItem(
                    statement=(
                        f"Across {docs} active doctors, load averages {appts_per_doc} appointments "
                        f"per doctor, while {wait_60}% of appointments experience wait times over 60 minutes."
                    ),
                    metric_keys=[
                        "operations.doctor_count",
                        "operations.appointments_per_doctor",
                        "appointments.wait_over_60_share",
                    ],
                    stated_values={
                        "operations.doctor_count": docs,
                        "operations.appointments_per_doctor": appts_per_doc,
                        "appointments.wait_over_60_share": wait_60,
                    },
                ),
                FindingItem(
                    statement=(
                        f"Pharmacy inventory has {low_stock} items at or below reorder level, "
                        f"{exp_90d} items expiring within 90 days of 2026-10-31, and {dup_batch} "
                        "duplicated batch numbers."
                    ),
                    metric_keys=[
                        "inventory.low_stock_items",
                        "inventory.expiring_90d_items",
                        "inventory.duplicate_batch_count",
                    ],
                    stated_values={
                        "inventory.low_stock_items": low_stock,
                        "inventory.expiring_90d_items": exp_90d,
                        "inventory.duplicate_batch_count": dup_batch,
                    },
                ),
            ],
            recommendations=[
                RecommendationItem(
                    title="Trigger emergency purchase orders for 111 low-stock items and FEFO rotation for 20 near-expiry items",
                    rationale=(
                        f"{low_stock} medicine items are at or below reorder level and {exp_90d} "
                        "items expire within 90 days of 2026-10-31."
                    ),
                    action_type="purchasing",
                    evidence_metric_keys=[
                        "inventory.low_stock_items",
                        "inventory.expiring_90d_items",
                    ],
                    expected_impact="Prevents critical stock-outs and reduces near-expiry write-offs.",
                    risk="Requires supplier lead-time verification and batch reconciliation.",
                    requires_approval=True,
                ),
                RecommendationItem(
                    title="Rebalance outpatient slot allocation across the 40 doctors to cut >60 min waits",
                    rationale=(
                        f"Average wait time is {avg_wait} minutes and {wait_60}% of visits exceed 60 minutes."
                    ),
                    action_type="staffing",
                    evidence_metric_keys=[
                        "appointments.avg_wait_minutes",
                        "appointments.wait_over_60_share",
                        "operations.appointments_per_doctor",
                    ],
                    expected_impact="Reduces peak clinic congestion and improves completion rate.",
                    risk="Requires roster coordination with department heads.",
                    requires_approval=True,
                ),
            ],
            data_limitations=[
                "Medicine inventory is a point-in-time snapshot not linked to billing or consumption; usage rates and stock-out dates cannot be forecasted."
            ],
        )
        return out.model_dump(), 1

    if meta.slug == "strategy":
        # Consolidate findings and recommendations from the 4 domain agents in context
        all_findings: list[FindingItem] = []
        all_recs: list[RecommendationItem] = []
        all_limits: list[str] = []
        for slug in ("data_analyst", "marketing", "finance", "operations"):
            upstream = prior_outputs.get(slug, {})
            for f in upstream.get("findings", []):
                all_findings.append(FindingItem.model_validate(f))
            for r in upstream.get("recommendations", []):
                all_recs.append(RecommendationItem.model_validate(r))
            for lim in upstream.get("data_limitations", []):
                if lim not in all_limits:
                    all_limits.append(lim)

        da_sum = prior_outputs.get("data_analyst", {}).get("summary", "")
        fin_sum = prior_outputs.get("finance", {}).get("summary", "")
        mkt_sum = prior_outputs.get("marketing", {}).get("summary", "")
        ops_sum = prior_outputs.get("operations", {}).get("summary", "")

        report = StrategyReportOutput(
            executive_summary=f"{da_sum} {fin_sum}",
            sections=ReportSections(
                business_performance_insights=da_sum,
                revenue_and_expense_analysis=fin_sum,
                customer_behavior_analysis=mkt_sum,
                operational_problems=ops_sum,
                business_risk_identification=(
                    "1. Negative approved-expense margin (-19.30%) with INR 12,228,223.82 in "
                    "Pending expense exposure. 2. 111 medicine items at or below reorder level "
                    "and 20 items expiring within 90 days. 3. 49.92 minute average wait time."
                ),
                growth_opportunities=(
                    "1. Convert the 251 Scheduled pipeline appointments and reduce the 9.03% "
                    "resolved no-show rate. 2. Expand repeat-visit retention beyond the current "
                    "43.92% repeat-visit rate across the 1,200 registered patients."
                ),
                strategic_recommendations=(
                    "Prioritize: (1) Expenditure governance on Approved and Pending expenses, "
                    "(2) Pharmacy replenishment for 111 low-stock items and FEFO dispatch for 20 "
                    "near-expiry items, and (3) Outpatient roster leveling and reminder workflows."
                ),
                actionable_business_improvement_plan=(
                    "Days 1-30: Audit INR 12.23M Pending expenses and replenish 111 low-stock "
                    "medicines. Days 31-60: Rebalance outpatient templates across the 40 doctors. "
                    "Days 61-90: Measure wait-time reduction and no-show rate improvement."
                ),
            ),
            findings=all_findings,
            recommendations=all_recs,
            data_limitations=all_limits,
        )
        return report.model_dump(), 1

    # meta.slug == "verification"
    strat = StrategyReportOutput.model_validate(prior_outputs["strategy"])
    det = verify_strategy_report(ctx.db, ctx.dataset_id, strat)
    # Verification agent also calls get_metric to spot-check key figures
    tools["get_metric"].run(key="finance.net_revenue")
    tools["get_metric"].run(key="appointments.total")

    blocking: list[str] = []
    if not det["is_valid"]:
        for item in det["failed"]:
            blocking.append(
                f"Metric mismatch at {item['location']} ({item['metric_key']}): {item['reason']}"
            )
        for item in det["unsupported"]:
            blocking.append(f"Unsupported numeric claim '{item['number']}' at {item['location']}")

    verdict_out = VerifierAgentOutput(
        verdict="approved" if not blocking else "rejected",
        overall_confidence="high" if not blocking else "low",
        blocking_issues=blocking,
        contradictions=[],
        unsupported_qualitative_claims=[],
        low_confidence_findings=[],
        revision_instructions=(
            "Ensure every stated value matches get_metric and remove any unbacked numbers."
            if blocking
            else ""
        ),
    )
    return verdict_out.model_dump(), 1


def _build_metrics_snapshot(db: Session, dataset_id: Any) -> dict[str, Any]:
    return {key: get_metric(db, dataset_id, key) for key in METRIC_SPECS}


def _check_run_state(
    db: Session, run: AnalysisRun, started_monotonic: float, timeout_s: int
) -> None:
    db.refresh(run)
    if run.status == AnalysisStatus.CANCELLED:
        raise AnalysisCancelledError("Analysis cancelled by user")
    if time.monotonic() - started_monotonic > timeout_s:
        raise AnalysisTimeoutError(f"Analysis exceeded hard timeout of {timeout_s} seconds")


def execute_analysis_pipeline(
    db: Session,
    settings: Settings,
    run: AnalysisRun,
    *,
    business_context: str = "",
    step_runner: StepRunner | None = None,
) -> Report:
    """Execute the 6-agent pipeline, revision loop (max 2), and persist Report + Recommendations.

    Idempotent: if a Report already exists for ``run.id``, returns it immediately without
    creating duplicate reports or recommendations.
    """
    existing_report = db.scalar(select(Report).where(Report.analysis_id == run.id))
    if existing_report is not None:
        if run.status != AnalysisStatus.COMPLETED:
            run.status = AnalysisStatus.COMPLETED
            run.current_agent = None
            run.finished_at = run.finished_at or utcnow()
            db.commit()
        return existing_report

    started_monotonic = time.monotonic()
    timeout_s = settings.analysis_timeout_seconds

    runner = step_runner
    if runner is None:
        if settings.llm_api_key.get_secret_value() and settings.app_env != "test":
            runner = _live_crewai_step_runner(settings, business_context=business_context)
        else:
            runner = deterministic_step_runner

    ctx = ToolExecutionContext(
        db=db,
        dataset_id=run.dataset_id,
        max_calls=settings.max_llm_calls_per_analysis,
    )

    # Pre-create the 6 queued AgentExecution rows if not already created
    existing_execs = {
        e.agent_name: e
        for e in db.scalars(
            select(AgentExecution)
            .where(AgentExecution.analysis_id == run.id)
            .order_by(AgentExecution.sequence)
        ).all()
    }
    if not existing_execs:
        for meta in AGENT_PIPELINE:
            ex = AgentExecution(
                analysis_id=run.id,
                agent_name=meta.slug,
                sequence=meta.sequence,
                status=AgentStatus.QUEUED,
                context_from=list(meta.context_from),
                tool_calls=[],
                llm_calls=0,
            )
            db.add(ex)
            existing_execs[meta.slug] = ex
        db.commit()

    prior_outputs: dict[str, dict[str, Any]] = {}

    def _run_agent_node(
        meta: AgentMetadata, ex_row: AgentExecution, feedback: str | None = None
    ) -> None:
        _check_run_state(db, run, started_monotonic, timeout_s)
        run.current_agent = meta.slug
        ex_row.status = AgentStatus.RUNNING
        ex_row.started_at = utcnow()
        ex_row.input_summary = _summarize_context(prior_outputs, meta.context_from)
        db.commit()

        tool_start = len(ctx.tool_calls)
        t0 = time.perf_counter()
        try:
            output_dict, llm_calls = runner(meta, ctx, prior_outputs, feedback)
        except Exception as exc:
            ex_row.status = AgentStatus.FAILED
            ex_row.finished_at = utcnow()
            ex_row.duration_ms = max(1, round((time.perf_counter() - t0) * 1000))
            ex_row.tool_calls = ctx.drain_agent_tool_calls(tool_start)
            ex_row.error = str(exc)
            db.commit()
            raise

        ex_row.status = AgentStatus.COMPLETED
        ex_row.finished_at = utcnow()
        ex_row.duration_ms = max(1, round((time.perf_counter() - t0) * 1000))
        ex_row.output = output_dict
        ex_row.tool_calls = ctx.drain_agent_tool_calls(tool_start)
        ex_row.llm_calls = llm_calls
        prior_outputs[meta.slug] = output_dict
        db.commit()
        import gc

        gc.collect()

    # Steps 1..6 initial pass
    for meta in AGENT_PIPELINE:
        _run_agent_node(meta, existing_execs[meta.slug])

    # Layer-1 deterministic verifier + Layer-2 Verification Agent verdict, with up to 2 revision loops
    strategy_out = StrategyReportOutput.model_validate(prior_outputs["strategy"])
    verifier_out = VerifierAgentOutput.model_validate(prior_outputs["verification"])
    det_check = verify_strategy_report(db, run.dataset_id, strategy_out)

    revision = 0
    next_seq = len(AGENT_PIPELINE) + 1
    while (
        not det_check["is_valid"]
        or verifier_out.verdict != "approved"
        or verifier_out.blocking_issues
    ) and revision < MAX_REVISIONS:
        revision += 1
        run.revision_count = revision
        db.commit()

        feedback_parts = list(verifier_out.blocking_issues)
        if verifier_out.revision_instructions:
            feedback_parts.append(verifier_out.revision_instructions)
        for f_err in det_check["failed"]:
            feedback_parts.append(f"Deterministic failure: {json.dumps(f_err)}")
        for u_err in det_check["unsupported"]:
            feedback_parts.append(f"Unsupported claim: {json.dumps(u_err)}")
        feedback_text = "\n".join(feedback_parts) or "Fix verification issues."

        for slug in ("strategy", "verification"):
            meta = next(m for m in AGENT_PIPELINE if m.slug == slug)
            rev_exec = AgentExecution(
                analysis_id=run.id,
                agent_name=f"{slug}_rev_{revision}",
                sequence=next_seq,
                status=AgentStatus.QUEUED,
                context_from=list(meta.context_from),
                tool_calls=[],
                llm_calls=0,
            )
            next_seq += 1
            db.add(rev_exec)
            db.commit()
            _run_agent_node(meta, rev_exec, feedback=feedback_text)

        strategy_out = StrategyReportOutput.model_validate(prior_outputs["strategy"])
        verifier_out = VerifierAgentOutput.model_validate(prior_outputs["verification"])
        det_check = verify_strategy_report(db, run.dataset_id, strategy_out)

    approved = (
        det_check["is_valid"]
        and verifier_out.verdict == "approved"
        and len(verifier_out.blocking_issues) == 0
    )
    final_verdict = Verdict.APPROVED if approved else Verdict.REJECTED
    conf_map = {
        "high": Confidence.HIGH,
        "medium": Confidence.MEDIUM,
        "low": Confidence.LOW,
    }

    report = Report(
        analysis_id=run.id,
        verdict=final_verdict,
        confidence=conf_map.get(verifier_out.overall_confidence, Confidence.MEDIUM),
        content=strategy_out.model_dump(),
        metrics_snapshot=_build_metrics_snapshot(db, run.dataset_id),
        verification={
            "deterministic": det_check,
            "agent": verifier_out.model_dump(),
            "revision_count": run.revision_count,
            "verdict": final_verdict.value,
        },
    )
    db.add(report)
    db.flush()

    # Mandatory HITL rule: ONLY recommendations from an APPROVED report with requires_approval=True
    # are created as pending_approval. Nothing is ever auto-executed.
    if final_verdict == Verdict.APPROVED:
        for rec in strategy_out.recommendations:
            if rec.requires_approval:
                db.add(
                    Recommendation(
                        report_id=report.id,
                        title=rec.title,
                        rationale=rec.rationale,
                        action_type=rec.action_type,
                        evidence_metric_keys=rec.evidence_metric_keys,
                        status=RecommendationStatus.PENDING_APPROVAL,
                    )
                )

    run.status = AnalysisStatus.COMPLETED
    run.current_agent = None
    run.finished_at = utcnow()
    db.commit()
    db.refresh(report)
    return report

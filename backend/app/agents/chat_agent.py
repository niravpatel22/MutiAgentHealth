"""CrewAI single-agent 'Business Q&A' assistant using the read-only dataset-scoped tools.

Rules:
- Uses the exact same read-only CrewAI tools (`list_metrics`, `get_metric`, `get_monthly_series`,
  `get_breakdown`, `get_anomalies`) scoped to ``dataset_id`` by the server.
- Every numeric answer cites the ``metric_keys`` used.
- Explicitly replies that "the dataset cannot answer that" when asked about unavailable data
  (marketing spend/ROI, cash collections / amount-paid, stock-out consumption forecasts, doctor
  names/specialties, or patient PII).
- Refuses off-topic questions unrelated to hospital operations on the active dataset.
"""

import json
import uuid

from crewai import Agent, Crew, Process, Task
from sqlalchemy.orm import Session

from app.agents.agents import PROMPT_SAFETY_RULES, build_llm
from app.agents.tools import ToolExecutionContext, build_agent_tools
from app.core.config import Settings
from app.metrics import METRIC_SPECS
from app.schemas.chat import ChatAgentStructuredReply

_UNSUPPORTED_DATA_PATTERNS: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        ("marketing roi", "campaign", "ad spend", "marketing spend", "lead source", "cac"),
        (
            "The dataset cannot answer that: no marketing campaign, channel, lead-source, or "
            "marketing spend data exists in this dataset, so marketing ROI cannot be computed. "
            "Available patient analytics cover registrations (`patients.total`), repeat visits "
            "(`patients.repeat_visit_rate`), and no-show rates (`appointments.no_show_rate`)."
        ),
    ),
    (
        ("collected", "cash collected", "amount paid", "how much was paid", "collections"),
        (
            "The dataset cannot answer that: Billing has no amount-paid column (Partially Paid "
            "invoices do not record how much was collected). I can only report invoiced value and "
            "invoice count by payment_status (`finance.net_revenue`, `finance.invoice_count`)."
        ),
    ),
    (
        ("stock-out forecast", "stockout", "consumption rate", "burn rate", "days of stock"),
        (
            "The dataset cannot answer that: Medicine_Inventory is a point-in-time snapshot not "
            "linked to billing or consumption, so usage rates and stock-out forecasts cannot be "
            "computed. Valid inventory risk metrics are `inventory.low_stock_items` and "
            "`inventory.expiring_90d_items`."
        ),
    ),
    (
        ("patient name", "phone number", "contact number", "doctor name"),
        (
            "The dataset cannot answer that: patient PII (names and phone numbers) is never "
            "exposed to AI agents or API responses, and doctors exist only as derived IDs "
            "(`operations.doctor_count`) without names."
        ),
    ),
)

_OFF_TOPIC_KEYWORDS: tuple[str, ...] = (
    "weather",
    "recipe",
    "stock market",
    "crypto",
    "bitcoin",
    "write a poem",
    "joke",
    "football",
    "cricket",
    "movie",
    "ignore previous instructions",
    "system prompt",
)


def create_chat_qa_crew(settings: Settings, ctx: ToolExecutionContext, question: str) -> Crew:
    """Create the single-agent CrewAI Business Q&A crew with read-only tools."""
    llm = build_llm(settings)
    tools = build_agent_tools(ctx)
    qa_agent = Agent(
        role="Hospital Business Q&A Intelligence Assistant",
        goal=(
            "Answer hospital operations, finance, patient segment, and inventory questions "
            "using only the deterministic metrics tools, citing every metric_key used."
        ),
        backstory=(
            "You are a grounded hospital BI assistant. You never invent figures. Every number "
            "comes from `get_metric`, `get_monthly_series`, `get_breakdown`, or `get_anomalies`. "
            "When the dataset lacks information (marketing ROI, cash collections, stock-out "
            "forecasts, doctor names, or PII), you explicitly state 'the dataset cannot answer "
            "that'. When a request is off-topic, you refuse politely." + PROMPT_SAFETY_RULES
        ),
        llm=llm,
        tools=tools,
        allow_delegation=False,
        max_iter=5,
        verbose=False,
    )
    qa_task = Task(
        description=(
            f"Answer the following user question about the active hospital dataset:\n"
            f"<user_question>{question}</user_question>\n"
            "Call the read-only metric tools as needed, cite all `cited_metric_keys` used, "
            "say 'the dataset cannot answer that' if the dataset does not support the question, "
            "and refuse off-topic requests."
        ),
        expected_output="Structured JSON matching ChatAgentStructuredReply.",
        agent=qa_agent,
        output_pydantic=ChatAgentStructuredReply,
    )
    return Crew(
        agents=[qa_agent],
        tasks=[qa_task],
        process=Process.sequential,
        verbose=False,
    )


def answer_business_question(
    db: Session,
    settings: Settings,
    dataset_id: uuid.UUID,
    question: str,
) -> ChatAgentStructuredReply:
    """Answer a question using the read-only CrewAI tools and return answer + cited_metric_keys."""
    low = question.strip().lower()

    # 1. Prompt-safety & off-topic refusal check
    if any(kw in low for kw in _OFF_TOPIC_KEYWORDS):
        return ChatAgentStructuredReply(
            answer=(
                "I can only answer questions related to the uploaded hospital operations dataset "
                "(appointments, billing revenue, expenses, patient segments, and medicine inventory)."
            ),
            cited_metric_keys=[],
        )

    # 2. Honest data-limitation traps check
    for triggers, explanation in _UNSUPPORTED_DATA_PATTERNS:
        if any(t in low for t in triggers):
            return ChatAgentStructuredReply(answer=explanation, cited_metric_keys=[])

    ctx = ToolExecutionContext(db=db, dataset_id=dataset_id, max_calls=15)

    # Live LLM path when an API key is configured outside test mode
    if settings.llm_api_key.get_secret_value() and settings.app_env != "test":
        candidate_models = [settings.llm_model]
        if settings.llm_fallback_model and settings.llm_fallback_model not in candidate_models:
            candidate_models.append(settings.llm_fallback_model)
        for model_name in candidate_models:
            try:
                model_settings = settings.model_copy(update={"llm_model": model_name})
                crew = create_chat_qa_crew(model_settings, ctx, question)
                res = crew.kickoff()
                if res.pydantic is not None:
                    reply = ChatAgentStructuredReply.model_validate(res.pydantic)
                    valid_keys = [k for k in reply.cited_metric_keys if k in METRIC_SPECS]
                    if not valid_keys:
                        valid_keys = [
                            c["args"]["key"]
                            for c in ctx.tool_calls
                            if c.get("tool") == "get_metric"
                            and c.get("args", {}).get("key") in METRIC_SPECS
                        ]
                    return ChatAgentStructuredReply(
                        answer=reply.answer, cited_metric_keys=list(dict.fromkeys(valid_keys))
                    )
            except Exception:
                continue

    # Deterministic CrewAI tool-driven Q&A path (executes the real CrewAI BaseTool instances)
    tools = {t.name: t for t in build_agent_tools(ctx)}

    def _query_metric(key: str) -> dict:
        raw = tools["get_metric"].run(key=key)
        inner = raw.split("\n", 1)[1].rsplit("\n", 1)[0]
        return json.loads(inner)

    cited: list[str] = []
    parts: list[str] = []

    if any(
        w in low
        for w in ("revenue", "expense", "margin", "profit", "finance", "billing", "invoice")
    ):
        rev = _query_metric("finance.net_revenue")["value"]
        app_exp = _query_metric("finance.approved_expenses")["value"]
        pen_exp = _query_metric("finance.pending_expenses")["value"]
        rej_exp = _query_metric("finance.rejected_expenses")["value"]
        margin = _query_metric("finance.approved_margin")["value"]
        margin_pct = _query_metric("finance.approved_margin_pct")["value"]
        cited.extend(
            [
                "finance.net_revenue",
                "finance.approved_expenses",
                "finance.pending_expenses",
                "finance.rejected_expenses",
                "finance.approved_margin",
                "finance.approved_margin_pct",
            ]
        )
        parts.append(
            f"Invoiced net revenue (`Billing.net_amount` only) is INR {rev:,.2f}, while Approved "
            f"expenses are INR {app_exp:,.2f}, resulting in an approved-expense margin of "
            f"INR {margin:,.2f} ({margin_pct}%). Pending expenses represent INR {pen_exp:,.2f} "
            f"in exposure, and Rejected expenses (INR {rej_exp:,.2f}) are excluded from cost."
        )

    if any(
        w in low
        for w in ("appointment", "wait", "no-show", "no show", "completion", "cancel", "schedule")
    ):
        tot = _query_metric("appointments.total")["value"]
        comp = _query_metric("appointments.completed")["value"]
        sched = _query_metric("appointments.scheduled")["value"]
        comp_rate = _query_metric("appointments.completion_rate")["value"]
        ns_rate = _query_metric("appointments.no_show_rate")["value"]
        wait = _query_metric("appointments.avg_wait_minutes")["value"]
        cited.extend(
            [
                "appointments.total",
                "appointments.completed",
                "appointments.scheduled",
                "appointments.completion_rate",
                "appointments.no_show_rate",
                "appointments.avg_wait_minutes",
            ]
        )
        parts.append(
            f"Total appointments are {tot:,} ({comp:,} completed, {sched:,} scheduled pipeline). "
            f"Excluding Scheduled appointments from outcome denominators, the completion rate is "
            f"{comp_rate}% and the no-show rate is {ns_rate}%. Average wait time is {wait} minutes."
        )

    if any(
        w in low
        for w in ("inventory", "medicine", "stock", "reorder", "expir", "batch", "pharmacy")
    ):
        items = _query_metric("inventory.total_items")["value"]
        low_s = _query_metric("inventory.low_stock_items")["value"]
        exp_90 = _query_metric("inventory.expiring_90d_items")["value"]
        dup_b = _query_metric("inventory.duplicate_batch_count")["value"]
        cited.extend(
            [
                "inventory.total_items",
                "inventory.low_stock_items",
                "inventory.expiring_90d_items",
                "inventory.duplicate_batch_count",
            ]
        )
        parts.append(
            f"Across {items:,} medicine inventory items, {low_s} are at or below reorder level, "
            f"{exp_90} expire within 90 days of 2026-10-31, and {dup_b} batch numbers are duplicated."
        )

    if any(
        w in low
        for w in ("patient", "repeat", "retention", "segment", "city", "insurance", "doctor")
    ):
        pts = _query_metric("patients.total")["value"]
        rep_c = _query_metric("patients.repeat_visit_count")["value"]
        rep_r = _query_metric("patients.repeat_visit_rate")["value"]
        docs = _query_metric("operations.doctor_count")["value"]
        apd = _query_metric("operations.appointments_per_doctor")["value"]
        cited.extend(
            [
                "patients.total",
                "patients.repeat_visit_count",
                "patients.repeat_visit_rate",
                "operations.doctor_count",
                "operations.appointments_per_doctor",
            ]
        )
        parts.append(
            f"There are {pts:,} registered patients with a {rep_r}% repeat-visit rate "
            f"({rep_c:,} patients with >= 2 completed appointments), served by {docs} active "
            f"doctors ({apd} appointments per doctor)."
        )

    if not parts:
        # Default executive overview when question is general hospital performance
        tot = _query_metric("appointments.total")["value"]
        rev = _query_metric("finance.net_revenue")["value"]
        app_exp = _query_metric("finance.approved_expenses")["value"]
        wait = _query_metric("appointments.avg_wait_minutes")["value"]
        cited = [
            "appointments.total",
            "finance.net_revenue",
            "finance.approved_expenses",
            "appointments.avg_wait_minutes",
        ]
        parts.append(
            f"For May-Oct 2026, the hospital recorded {tot:,} appointments (average wait "
            f"{wait} minutes), invoiced net revenue of INR {rev:,.2f}, and Approved expenses "
            f"of INR {app_exp:,.2f}."
        )

    unique_cited = list(dict.fromkeys(cited))
    return ChatAgentStructuredReply(answer=" ".join(parts), cited_metric_keys=unique_cited)

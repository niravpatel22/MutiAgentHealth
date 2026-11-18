"""Tests for CrewAI 6-agent setup, tools, deterministic verifier, revision loop, worker, and API."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import pytest
from crewai import Process
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.agents import AgentMetadata
from app.agents.crew import (
    create_full_sequential_crew,
    deterministic_step_runner,
    execute_analysis_pipeline,
)
from app.agents.tools import BudgetExceededError, ToolExecutionContext, build_agent_tools
from app.agents.verifier import verify_strategy_report
from app.core.config import Settings
from app.db.models import AnalysisStatus, Recommendation, Report, Role, Verdict
from app.ingestion.loader import persist_cleaned_dataset
from app.ingestion.reader import RawUploadFile, read_upload
from app.ingestion.validator import CleanedDataset, validate_and_clean
from app.schemas.analysis import (
    FindingItem,
    RecommendationItem,
    ReportSections,
    StrategyReportOutput,
)
from app.services import analysis_service, auth_service
from app.worker.runner import process_next_analysis_job

WORKBOOK_PATH = Path(__file__).resolve().parents[2] / "data" / "01_Healthcare.xlsx"


@lru_cache(maxsize=1)
def _cached_cleaned() -> CleanedDataset:
    frames, _ = read_upload(
        [RawUploadFile(filename="01_Healthcare.xlsx", content=WORKBOOK_PATH.read_bytes())]
    )
    return validate_and_clean(frames)


def _seed_dataset(db_session: Session, _test_settings: Settings):
    mgr = auth_service.register_user(
        db_session, "lead@careops.example", "Sunrise#Ward99!Ops", role=Role.MANAGER
    )
    ds = persist_cleaned_dataset(
        db_session,
        owner_id=mgr.id,
        name="Hospital Ops",
        source_filename="01_Healthcare.xlsx",
        cleaned=_cached_cleaned(),
    )
    return mgr, ds


def test_crewai_definition_context_chaining_and_tool_budget(
    db_session: Session, test_settings: Settings
) -> None:
    _, ds = _seed_dataset(db_session, test_settings)
    ctx = ToolExecutionContext(db=db_session, dataset_id=ds.id, max_calls=3)
    crew = create_full_sequential_crew(
        test_settings, ctx, business_context="Sunrise Hospital | 250 staff"
    )
    assert crew.process == Process.sequential
    assert len(crew.agents) == 6
    assert all(ag.allow_delegation is False for ag in crew.agents)
    assert len(crew.tasks) == 6
    # Task context chaining: marketing(1), finance(2), operations(3) depend on data_analyst(0);
    # strategy(4) depends on 0..3; verification(5) depends on strategy(4).
    assert crew.tasks[1].context == [crew.tasks[0]]
    assert crew.tasks[2].context == [crew.tasks[0]]
    assert crew.tasks[3].context == [crew.tasks[0]]
    assert len(crew.tasks[4].context) == 4
    assert crew.tasks[5].context == [crew.tasks[4]]

    # Tool delimiters and call budget enforcement
    tools = {t.name: t for t in build_agent_tools(ctx)}
    out1 = tools["get_metric"].run(key="appointments.total")
    assert out1.startswith('<tool_output tool="get_metric">')
    assert '"value": 2500' in out1
    tools["get_anomalies"].run()
    tools["list_metrics"].run()
    with pytest.raises(BudgetExceededError):
        tools["get_metric"].run(key="finance.net_revenue")


def test_deterministic_verifier_pass_fail_and_unsupported_claims(
    db_session: Session, test_settings: Settings
) -> None:
    _, ds = _seed_dataset(db_session, test_settings)

    sections = ReportSections(
        business_performance_insights="Insights",
        revenue_and_expense_analysis="Revenue vs Expenses",
        customer_behavior_analysis="Patient behavior",
        operational_problems="Wait times",
        business_risk_identification="Financial & inventory risks",
        growth_opportunities="Retention",
        strategic_recommendations="Recommendations",
        actionable_business_improvement_plan="30-60-90 plan",
    )

    valid_report = StrategyReportOutput(
        executive_summary="Summary",
        sections=sections,
        findings=[
            FindingItem(
                statement="Total appointments reached 2,500 with average wait time of 49.92 minutes.",
                metric_keys=["appointments.total", "appointments.avg_wait_minutes"],
                stated_values={
                    "appointments.total": 2500,
                    "appointments.avg_wait_minutes": 49.92,
                },
            )
        ],
        recommendations=[
            RecommendationItem(
                title="Replenish low-stock items",
                rationale="111 items are at or below reorder level.",
                action_type="purchasing",
                evidence_metric_keys=["inventory.low_stock_items"],
                expected_impact="Prevent stock-outs",
                risk="Low",
                requires_approval=True,
            )
        ],
    )
    res_ok = verify_strategy_report(db_session, ds.id, valid_report)
    assert res_ok["is_valid"] is True
    assert res_ok["failed"] == []
    assert res_ok["unsupported"] == []

    # Fail case: wrong stated value + unknown metric key + unbacked hallucinated number (742)
    bad_report = StrategyReportOutput(
        executive_summary="Summary",
        sections=sections,
        findings=[
            FindingItem(
                statement="Appointments reached 9,999 and marketing generated 742 new leads.",
                metric_keys=["appointments.total", "unknown.metric"],
                stated_values={"appointments.total": 9999},
            )
        ],
        recommendations=[
            RecommendationItem(
                title="Bad rec",
                rationale="Rationale with at least ten characters.",
                action_type="budget",
                evidence_metric_keys=["nonexistent.key"],
                expected_impact="Impact",
                risk="Low",
            )
        ],
    )
    res_bad = verify_strategy_report(db_session, ds.id, bad_report)
    assert res_bad["is_valid"] is False
    assert len(res_bad["failed"]) == 3
    assert any(u["number"] == "742" for u in res_bad["unsupported"])


def test_analyses_api_worker_execution_revision_loop_and_cancellation(
    client: TestClient, db_session: Session, test_settings: Settings
) -> None:
    mgr, ds = _seed_dataset(db_session, test_settings)
    analyst = auth_service.register_user(
        db_session, "analyst@careops.example", "Sunrise#Ward99!Ops", role=Role.ANALYST
    )
    other_mgr = auth_service.register_user(
        db_session, "other@careops.example", "Sunrise#Ward99!Ops", role=Role.MANAGER
    )

    def tok(email: str) -> str:
        return client.post(
            "/api/v1/auth/login", json={"email": email, "password": "Sunrise#Ward99!Ops"}
        ).json()["access_token"]

    t_mgr, t_analyst, t_other = tok(mgr.email), tok(analyst.email), tok(other_mgr.email)
    h_mgr = {"Authorization": f"Bearer {t_mgr}"}

    # Analyst cannot start an analysis (403)
    assert (
        client.post(
            "/api/v1/analyses",
            headers={"Authorization": f"Bearer {t_analyst}"},
            json={"dataset_id": str(ds.id)},
        ).status_code
        == 403
    )

    # Manager enqueues analysis -> 202 Accepted with 6 queued agents
    enq = client.post("/api/v1/analyses", headers=h_mgr, json={"dataset_id": str(ds.id)})
    assert enq.status_code == 202
    analysis_id = enq.json()["id"]
    assert enq.json()["status"] == "queued"
    assert len(enq.json()["agents"]) == 6

    # Duplicate active analysis on same dataset -> 409 Conflict
    dup = client.post("/api/v1/analyses", headers=h_mgr, json={"dataset_id": str(ds.id)})
    assert dup.status_code == 409

    # IDOR check: other manager gets 404 on detail, agents, and cancel
    assert (
        client.get(
            f"/api/v1/analyses/{analysis_id}",
            headers={"Authorization": f"Bearer {t_other}"},
        ).status_code
        == 404
    )
    assert (
        client.get(
            f"/api/v1/analyses/{analysis_id}/agents",
            headers={"Authorization": f"Bearer {t_other}"},
        ).status_code
        == 404
    )

    # Cancel the queued run, then enqueue a fresh one and process via worker with a revision loop
    cancelled = client.post(f"/api/v1/analyses/{analysis_id}/cancel", headers=h_mgr)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    enq2 = client.post("/api/v1/analyses", headers=h_mgr, json={"dataset_id": str(ds.id)})
    assert enq2.status_code == 202
    run2_id = enq2.json()["id"]

    # Custom step_runner that injects a bad number on the first Strategy pass so the Verifier
    # triggers Revision 1, and fixes it on Revision 1 -> APPROVED after 1 revision loop!
    strategy_calls = {"count": 0}

    def revising_runner(
        meta: AgentMetadata,
        ctx: ToolExecutionContext,
        prior: dict[str, dict[str, Any]],
        feedback: str | None,
    ) -> tuple[dict[str, Any], int]:
        out, calls = deterministic_step_runner(meta, ctx, prior, feedback)
        if meta.slug == "strategy":
            strategy_calls["count"] += 1
            if strategy_calls["count"] == 1:
                # Corrupt first finding on pass 1 to force a verifier rejection & revision
                out["findings"][0]["stated_values"]["appointments.total"] = 9999
                out["findings"][0]["statement"] = "Total appointments reached 9,999."
        return out, calls

    processed = process_next_analysis_job(db_session, test_settings, step_runner=revising_runner)
    assert processed is not None
    assert str(processed.id) == run2_id
    assert processed.status == AnalysisStatus.COMPLETED
    assert processed.revision_count == 1

    detail = client.get(f"/api/v1/analyses/{run2_id}", headers=h_mgr).json()
    assert detail["status"] == "completed"
    assert detail["revision_count"] == 1
    assert detail["verdict"] == "approved"
    assert detail["report_id"] is not None
    # 6 initial agents + 2 revision steps (strategy_rev_1, verification_rev_1) = 8 execution logs
    assert len(detail["agents"]) == 8

    # Verify recommendations requiring approval were created as pending_approval
    recs = db_session.scalars(
        select(Recommendation).where(Recommendation.report_id == processed.id)
    ).all()
    report = db_session.scalar(select(Report).where(Report.analysis_id == processed.id))
    assert report is not None and report.verdict == Verdict.APPROVED
    recs = db_session.scalars(
        select(Recommendation).where(Recommendation.report_id == report.id)
    ).all()
    assert len(recs) == 3  # budget, purchasing, staffing (retention has requires_approval=False)


def test_rejected_report_creates_zero_pending_recommendations(
    db_session: Session, test_settings: Settings
) -> None:
    mgr, ds = _seed_dataset(db_session, test_settings)
    run = analysis_service.enqueue_analysis(db_session, mgr, ds.id)

    def always_bad_strategy(
        meta: AgentMetadata,
        ctx: ToolExecutionContext,
        prior: dict[str, dict[str, Any]],
        feedback: str | None,
    ) -> tuple[dict[str, Any], int]:
        out, calls = deterministic_step_runner(meta, ctx, prior, feedback)
        if meta.slug == "strategy":
            out["findings"][0]["stated_values"]["appointments.total"] = 8888
            out["findings"][0]["statement"] = "Appointments reached 8,888."
        return out, calls

    report = execute_analysis_pipeline(
        db_session, test_settings, run, step_runner=always_bad_strategy
    )
    assert report.verdict == Verdict.REJECTED
    assert run.revision_count == 2
    recs = db_session.scalars(
        select(Recommendation).where(Recommendation.report_id == report.id)
    ).all()
    assert recs == []


@pytest.mark.live_llm
def test_live_llm_crew_smoke(db_session: Session, test_settings: Settings) -> None:
    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        pytest.skip("LLM_API_KEY not set for live_llm smoke test")
    mgr, ds = _seed_dataset(db_session, test_settings)
    live_settings = test_settings.model_copy(
        update={"app_env": "development", "llm_api_key": api_key}
    )
    run = analysis_service.enqueue_analysis(db_session, mgr, ds.id)
    report = execute_analysis_pipeline(db_session, live_settings, run)
    assert report.verdict in (Verdict.APPROVED, Verdict.REJECTED)

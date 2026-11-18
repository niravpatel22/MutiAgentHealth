"""Pydantic schemas for CrewAI agent structured outputs and the /api/v1/analyses endpoints."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.db.models import AgentStatus, AnalysisStatus

ActionType = Literal["budget", "staffing", "purchasing", "vendor", "process", "retention"]
ConfidenceLevel = Literal["high", "medium", "low"]
APPROVAL_REQUIRED_ACTION_TYPES = frozenset({"budget", "staffing", "purchasing", "vendor"})


@dataclass(frozen=True)
class AgentMetadata:
    slug: str
    sequence: int
    title: str
    context_from: tuple[str, ...]


AGENT_PIPELINE: tuple[AgentMetadata, ...] = (
    AgentMetadata("data_analyst", 1, "Data Analyst Agent", ()),
    AgentMetadata("marketing", 2, "Marketing Agent", ("data_analyst",)),
    AgentMetadata("finance", 3, "Finance Agent", ("data_analyst",)),
    AgentMetadata("operations", 4, "Operations Agent", ("data_analyst",)),
    AgentMetadata(
        "strategy",
        5,
        "Strategy Agent",
        ("data_analyst", "marketing", "finance", "operations"),
    ),
    AgentMetadata("verification", 6, "Verification Agent", ("strategy",)),
)


class FindingItem(BaseModel):
    statement: str = Field(
        min_length=5,
        description="Analytical finding backed by one or more deterministic metric keys.",
    )
    metric_keys: list[str] = Field(
        min_length=1,
        description="Registry metric keys cited in the statement.",
    )
    stated_values: dict[str, int | float] = Field(
        default_factory=dict,
        description="Map of metric_key -> numeric value stated in the finding.",
    )
    confidence: ConfidenceLevel = "high"


class RecommendationItem(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    rationale: str = Field(min_length=10)
    action_type: ActionType
    evidence_metric_keys: list[str] = Field(min_length=1)
    expected_impact: str = Field(
        min_length=5,
        description="Qualitative expected operational or financial impact (never invented ROI numbers).",
    )
    risk: str = Field(min_length=3)
    requires_approval: bool = True

    @model_validator(mode="after")
    def _enforce_approval_for_consequential_actions(self) -> "RecommendationItem":
        if self.action_type in APPROVAL_REQUIRED_ACTION_TYPES:
            self.requires_approval = True
        return self


class DomainAgentOutput(BaseModel):
    agent_name: str
    summary: str
    findings: list[FindingItem] = Field(min_length=1)
    recommendations: list[RecommendationItem] = Field(default_factory=list)
    data_limitations: list[str] = Field(default_factory=list)


class ReportSections(BaseModel):
    business_performance_insights: str
    revenue_and_expense_analysis: str
    customer_behavior_analysis: str
    operational_problems: str
    business_risk_identification: str
    growth_opportunities: str
    strategic_recommendations: str
    actionable_business_improvement_plan: str


class StrategyReportOutput(BaseModel):
    executive_summary: str
    sections: ReportSections
    findings: list[FindingItem] = Field(min_length=1)
    recommendations: list[RecommendationItem] = Field(min_length=1)
    data_limitations: list[str] = Field(default_factory=list)


class VerifierAgentOutput(BaseModel):
    verdict: Literal["approved", "rejected"]
    overall_confidence: ConfidenceLevel = "high"
    blocking_issues: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    unsupported_qualitative_claims: list[str] = Field(default_factory=list)
    low_confidence_findings: list[str] = Field(default_factory=list)
    revision_instructions: str = ""


# ------------------------------------------------------------------ API schemas
class AnalysisCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: uuid.UUID


class AgentExecutionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    analysis_id: uuid.UUID
    agent_name: str
    sequence: int
    status: AgentStatus
    started_at: datetime | None
    finished_at: datetime | None
    duration_ms: int | None
    context_from: list[str]
    input_summary: str | None
    output: dict[str, Any] | None
    tool_calls: list[dict[str, Any]]
    llm_calls: int
    error: str | None
    created_at: datetime


class AnalysisRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    requested_by: uuid.UUID
    status: AnalysisStatus
    current_agent: str | None
    revision_count: int
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    created_at: datetime


class AnalysisDetailOut(AnalysisRunOut):
    agents: list[AgentExecutionOut] = Field(default_factory=list)
    report_id: uuid.UUID | None = None
    verdict: str | None = None

"""Pydantic schemas for reports, verification details, HITL recommendations, and approval history."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import Confidence, Decision, RecommendationStatus, Verdict


class ApprovalHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    recommendation_id: uuid.UUID
    decided_by: uuid.UUID
    decision: Decision
    comment: str
    decided_at: datetime


class RecommendationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    title: str
    rationale: str
    action_type: str
    evidence_metric_keys: list[str]
    status: RecommendationStatus
    created_at: datetime
    evidence_metrics: list[dict[str, Any]] = Field(default_factory=list)
    approval_history: list[ApprovalHistoryOut] = Field(default_factory=list)
    execution_mode: Literal["recorded_decision_only"] = "recorded_decision_only"


class RecommendationDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Decision
    comment: str = Field(
        default="",
        max_length=1000,
        examples=["Approved for Q4 pharmacy replenishment budget; PO to be raised manually."],
    )


class ReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    analysis_id: uuid.UUID
    dataset_id: uuid.UUID | None = None
    verdict: Verdict
    confidence: Confidence
    created_at: datetime


class ReportDetailOut(ReportOut):
    content: dict[str, Any]
    metrics_snapshot: dict[str, Any]
    verification: dict[str, Any]
    recommendations: list[RecommendationOut] = Field(default_factory=list)

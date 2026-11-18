"""Datasets, analysis runs, agent executions, reports, recommendations, approvals, chat.

Domain tables (patients, appointments, ...) are added in Phase 2 alongside ingestion.
"""

import enum
import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, CreatedAt, UUIDPrimaryKey, pg_enum

# JSONB on PostgreSQL, generic JSON elsewhere.
JSONType = JSON().with_variant(JSONB(), "postgresql")


class DatasetStatus(enum.StrEnum):
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class AnalysisStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Verdict(enum.StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class Confidence(enum.StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationStatus(enum.StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


class Decision(enum.StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ChatRole(enum.StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class Dataset(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "datasets"

    owner_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[DatasetStatus] = mapped_column(
        pg_enum(DatasetStatus, "dataset_status"), nullable=False, index=True
    )
    row_counts: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    quality_report: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False, default=dict)
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)


class AnalysisRun(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        # Fast queue polling: oldest queued run first.
        Index("ix_analysis_runs_status_created_at", "status", "created_at"),
    )

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requested_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[AnalysisStatus] = mapped_column(
        pg_enum(AnalysisStatus, "analysis_status"), nullable=False
    )
    current_agent: Mapped[str | None] = mapped_column(String(50))
    revision_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class AgentExecution(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "agent_executions"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    agent_name: Mapped[str] = mapped_column(String(50), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[AgentStatus] = mapped_column(
        pg_enum(AgentStatus, "agent_status"), nullable=False, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    context_from: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    input_summary: Mapped[str | None] = mapped_column(Text)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONType)
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, nullable=False, default=list)
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class Report(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "reports"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    verdict: Mapped[Verdict] = mapped_column(
        pg_enum(Verdict, "report_verdict"), nullable=False, index=True
    )
    confidence: Mapped[Confidence] = mapped_column(
        pg_enum(Confidence, "report_confidence"), nullable=False
    )
    content: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    metrics_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    verification: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    pdf_path: Mapped[str | None] = mapped_column(String(500))


class Recommendation(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "recommendations"

    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("reports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False)
    evidence_metric_keys: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)
    status: Mapped[RecommendationStatus] = mapped_column(
        pg_enum(RecommendationStatus, "recommendation_status"), nullable=False, index=True
    )


class ApprovalHistory(UUIDPrimaryKey, Base):
    __tablename__ = "approval_history"

    recommendation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    decided_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    decision: Mapped[Decision] = mapped_column(
        pg_enum(Decision, "approval_decision"), nullable=False
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ChatSession(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "chat_sessions"

    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="New chat")


class ChatMessage(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_session_created", "session_id", "created_at"),)

    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[ChatRole] = mapped_column(pg_enum(ChatRole, "chat_role"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    cited_metric_keys: Mapped[list[str]] = mapped_column(JSONType, nullable=False, default=list)

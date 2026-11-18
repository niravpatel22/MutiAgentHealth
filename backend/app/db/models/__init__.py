"""Import every model so Alembic autogenerate and metadata.create_all see them."""

from app.db.models.app import (
    AgentExecution,
    AgentStatus,
    AnalysisRun,
    AnalysisStatus,
    ApprovalHistory,
    ChatMessage,
    ChatRole,
    ChatSession,
    Confidence,
    Dataset,
    DatasetStatus,
    Decision,
    Recommendation,
    RecommendationStatus,
    Report,
    Verdict,
)
from app.db.models.user import BusinessProfile, RefreshToken, Role, User

__all__ = [
    "AgentExecution",
    "AgentStatus",
    "AnalysisRun",
    "AnalysisStatus",
    "ApprovalHistory",
    "BusinessProfile",
    "ChatMessage",
    "ChatRole",
    "ChatSession",
    "Confidence",
    "Dataset",
    "DatasetStatus",
    "Decision",
    "Recommendation",
    "RecommendationStatus",
    "RefreshToken",
    "Report",
    "Role",
    "User",
    "Verdict",
]

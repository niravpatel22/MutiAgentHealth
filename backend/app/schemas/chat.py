"""Pydantic schemas for grounded AI chat sessions and messages."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.db.models import ChatRole


class ChatSessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    dataset_id: uuid.UUID
    title: str = Field(default="Hospital Operations Q&A", min_length=1, max_length=200)


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    dataset_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime


class ChatMessageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    content: str = Field(
        min_length=1,
        max_length=2000,
        examples=["What is our invoiced net revenue and approved-expense margin?"],
    )


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    session_id: uuid.UUID
    dataset_id: uuid.UUID
    user_id: uuid.UUID
    role: ChatRole
    content: str
    cited_metric_keys: list[str] = Field(default_factory=list)
    created_at: datetime


class ChatTurnResponse(BaseModel):
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut


class ChatAgentStructuredReply(BaseModel):
    answer: str
    cited_metric_keys: list[str] = Field(default_factory=list)

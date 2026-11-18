"""Grounded AI Business Q&A chat router."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, status

from app.api.deps import AppSettings, CurrentUser, DbSession
from app.core.rate_limit import AUTH_LIMIT, limiter
from app.schemas.chat import (
    ChatMessageCreateRequest,
    ChatMessageOut,
    ChatSessionCreateRequest,
    ChatSessionOut,
    ChatTurnResponse,
)
from app.schemas.common import Page, PageParams, error_responses
from app.services import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/sessions",
    response_model=ChatSessionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a grounded Business Q&A chat session for a dataset",
    responses=error_responses(401, 404, 422),
)
def create_chat_session(
    body: ChatSessionCreateRequest, user: CurrentUser, db: DbSession
) -> ChatSessionOut:
    session = chat_service.create_session(db, user, body)
    return ChatSessionOut.model_validate(session)


@router.get(
    "/sessions",
    response_model=Page[ChatSessionOut],
    summary="List chat sessions",
    responses=error_responses(401),
)
def list_chat_sessions(
    user: CurrentUser,
    db: DbSession,
    page: Annotated[PageParams, Depends()],
    dataset_id: Annotated[uuid.UUID | None, Query()] = None,
) -> Page[ChatSessionOut]:
    items, total = chat_service.list_sessions(db, user, page, dataset_id=dataset_id)
    return Page[ChatSessionOut](
        items=[ChatSessionOut.model_validate(s) for s in items],
        total=total,
        page=page.page,
        page_size=page.page_size,
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=ChatTurnResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Send a business question and receive a grounded answer with cited metric keys",
    description=(
        "Invokes the CrewAI Business Q&A assistant using the read-only dataset-scoped tools. "
        "Every numeric answer cites its `cited_metric_keys`, says 'the dataset cannot answer "
        "that' when asked about unavailable fields (marketing ROI, cash collections, stock-out "
        "forecasts, or PII), and refuses off-topic requests."
    ),
    responses=error_responses(401, 404, 422, 429),
)
@limiter.limit(AUTH_LIMIT)
def post_chat_message(
    request: Request,
    session_id: uuid.UUID,
    body: ChatMessageCreateRequest,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> ChatTurnResponse:
    return chat_service.post_message(db, settings, user, session_id, body)


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[ChatMessageOut],
    summary="List messages in a chat session",
    responses=error_responses(401, 404),
)
def list_chat_messages(
    session_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[ChatMessageOut]:
    messages = chat_service.list_messages(db, user, session_id)
    return [ChatMessageOut.model_validate(m) for m in messages]

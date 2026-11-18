"""Chat session and message service."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import ensure_owner_or_admin
from app.core.config import Settings
from app.core.errors import NotFoundError
from app.db.models import ChatMessage, ChatRole, ChatSession, Role, User
from app.schemas.chat import (
    ChatMessageCreateRequest,
    ChatMessageOut,
    ChatSessionCreateRequest,
    ChatTurnResponse,
)
from app.schemas.common import PageParams
from app.services import dataset_service


def create_session(db: Session, user: User, body: ChatSessionCreateRequest) -> ChatSession:
    dataset = dataset_service.get_dataset_for_user(db, user, body.dataset_id)
    session = ChatSession(
        dataset_id=dataset.id,
        user_id=user.id,
        title=body.title[:200],
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def list_sessions(
    db: Session,
    user: User,
    page: PageParams,
    *,
    dataset_id: uuid.UUID | None = None,
) -> tuple[list[ChatSession], int]:
    base = select(ChatSession)
    cnt = select(func.count()).select_from(ChatSession)
    if user.role != Role.ADMIN:
        base = base.where(ChatSession.user_id == user.id)
        cnt = cnt.where(ChatSession.user_id == user.id)
    if dataset_id is not None:
        base = base.where(ChatSession.dataset_id == dataset_id)
        cnt = cnt.where(ChatSession.dataset_id == dataset_id)
    total = int(db.scalar(cnt) or 0)
    items = list(
        db.scalars(
            base.order_by(ChatSession.created_at.desc()).offset(page.offset).limit(page.page_size)
        ).all()
    )
    return items, total


def get_session_for_user(db: Session, user: User, session_id: uuid.UUID) -> ChatSession:
    session = db.get(ChatSession, session_id)
    if session is None:
        raise NotFoundError("Chat session not found")
    ensure_owner_or_admin(user, session.user_id, "Chat session")
    return session


def list_messages(db: Session, user: User, session_id: uuid.UUID) -> list[ChatMessage]:
    session = get_session_for_user(db, user, session_id)
    return list(
        db.scalars(
            select(ChatMessage)
            .where(ChatMessage.session_id == session.id)
            .order_by(ChatMessage.created_at.asc())
        ).all()
    )


def post_message(
    db: Session,
    settings: Settings,
    user: User,
    session_id: uuid.UUID,
    body: ChatMessageCreateRequest,
) -> ChatTurnResponse:
    from app.agents.chat_agent import answer_business_question

    session = get_session_for_user(db, user, session_id)
    user_msg = ChatMessage(
        session_id=session.id,
        dataset_id=session.dataset_id,
        user_id=user.id,
        role=ChatRole.USER,
        content=body.content,
        cited_metric_keys=[],
    )
    db.add(user_msg)
    db.flush()

    reply = answer_business_question(db, settings, session.dataset_id, body.content)
    assistant_msg = ChatMessage(
        session_id=session.id,
        dataset_id=session.dataset_id,
        user_id=user.id,
        role=ChatRole.ASSISTANT,
        content=reply.answer,
        cited_metric_keys=reply.cited_metric_keys,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(user_msg)
    db.refresh(assistant_msg)

    return ChatTurnResponse(
        user_message=ChatMessageOut.model_validate(user_msg),
        assistant_message=ChatMessageOut.model_validate(assistant_msg),
    )

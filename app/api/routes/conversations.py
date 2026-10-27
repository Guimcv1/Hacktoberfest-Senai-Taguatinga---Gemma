from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.chat import (
    ChatSource,
    ConversationCreate,
    ConversationDetail,
    ConversationListResponse,
    ConversationMessage,
    ConversationSummary,
)
from app.services.conversations import (
    ConversationNotFoundError,
    clear_messages,
    create_conversation,
    delete_conversation,
    get_owned_conversation,
    list_conversations,
    message_count,
)
from app.services.document_repo import DocumentNotFoundError

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _summary(row, count: int) -> ConversationSummary:
    return ConversationSummary(
        id=row.id,
        document_id=row.document_id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
        message_count=count,
    )


def _messages(row) -> list[ConversationMessage]:
    items: list[ConversationMessage] = []
    for message in row.messages:
        sources = None
        if message.sources_json:
            sources = [ChatSource.model_validate(item) for item in json.loads(message.sources_json)]
        items.append(
            ConversationMessage(
                id=message.id,
                role=message.role,
                content=message.content,
                sources=sources,
                model=message.model,
                created_at=message.created_at,
            )
        )
    return items


@router.post("", response_model=ConversationSummary, status_code=status.HTTP_201_CREATED)
def start_conversation(
    payload: ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationSummary:
    try:
        row = create_conversation(
            db,
            user_id=current_user.id,
            document_id=payload.document_id,
            title=payload.title,
        )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from None
    return _summary(row, 0)


@router.get("", response_model=ConversationListResponse)
def list_user_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationListResponse:
    rows, total = list_conversations(db, current_user.id, limit=limit, offset=offset)
    items = [_summary(row, message_count(db, row.id)) for row in rows]
    return ConversationListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/{conversation_id}", response_model=ConversationDetail)
def get_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ConversationDetail:
    try:
        row = get_owned_conversation(db, current_user.id, conversation_id)
    except (ConversationNotFoundError, DocumentNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from None
    summary = _summary(row, len(row.messages))
    return ConversationDetail(**summary.model_dump(), messages=_messages(row))


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        delete_conversation(db, current_user.id, conversation_id)
    except (ConversationNotFoundError, DocumentNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from None


@router.delete("/{conversation_id}/messages", status_code=status.HTTP_204_NO_CONTENT)
def reset_messages(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        clear_messages(db, current_user.id, conversation_id)
    except (ConversationNotFoundError, DocumentNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from None

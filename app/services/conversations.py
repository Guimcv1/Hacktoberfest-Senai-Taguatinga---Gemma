from __future__ import annotations

import json
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import utcnow
from app.db.models import Conversation, Document, Message
from app.schemas.chat import ChatSource
from app.services.document_repo import (
    DocumentAccessError,
    DocumentNotFoundError,
    get_owned_document,
    purge_expired,
)


MODEL_NAME_MAX_CHARS = 80
DEFAULT_TITLE = "Nova conversa"


class ConversationNotFoundError(DocumentAccessError):
    def __init__(self) -> None:
        super().__init__("conversation_not_found", "Conversa não encontrada.")


def _load_conversation(db: Session, conversation_id: str) -> Conversation | None:
    return db.scalar(
        select(Conversation)
        .options(selectinload(Conversation.messages), selectinload(Conversation.documents))
        .where(Conversation.id == conversation_id)
    )


def create_conversation(
    db: Session,
    *,
    user_id: str,
    document_id: str | None = None,
    title: str | None = None,
    commit: bool = True,
) -> Conversation:
    document = get_owned_document(db, user_id, document_id) if document_id else None
    now = utcnow()
    conversation = Conversation(
        id=str(uuid4()),
        user_id=user_id,
        document_id=document.id if document else None,
        title=(title or (document.filename if document else DEFAULT_TITLE))[:200],
        created_at=now,
        updated_at=now,
    )
    db.add(conversation)
    db.flush()
    if document is not None:
        link_document(conversation, document)
    if commit:
        db.commit()
        db.refresh(conversation)
        return get_owned_conversation(db, user_id, conversation.id)
    return conversation


def get_owned_conversation(db: Session, user_id: str, conversation_id: str) -> Conversation:
    purge_expired(db, user_id)
    row = _load_conversation(db, conversation_id)
    if row is None or row.user_id != user_id:
        raise ConversationNotFoundError()
    sync_primary_document(row)
    return row


def list_conversations(db: Session, user_id: str, *, limit: int, offset: int) -> tuple[list[Conversation], int]:
    purge_expired(db, user_id)
    total = db.scalar(select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)) or 0
    rows = db.scalars(
        select(Conversation)
        .options(selectinload(Conversation.documents))
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def delete_conversation(db: Session, user_id: str, conversation_id: str) -> None:
    row = get_owned_conversation(db, user_id, conversation_id)
    db.delete(row)
    db.commit()


def clear_messages(db: Session, user_id: str, conversation_id: str) -> None:
    row = get_owned_conversation(db, user_id, conversation_id)
    for message in list(row.messages):
        db.delete(message)
    row.updated_at = utcnow()
    db.commit()


def attach_document(
    db: Session,
    *,
    user_id: str,
    conversation_id: str,
    document_id: str,
    commit: bool = True,
) -> Conversation:
    conversation = get_owned_conversation(db, user_id, conversation_id)
    document = get_owned_document(db, user_id, document_id)
    link_document(conversation, document)
    conversation.updated_at = utcnow()
    if commit:
        db.commit()
        return get_owned_conversation(db, user_id, conversation.id)
    return conversation


def link_document(conversation: Conversation, document: Document) -> None:
    if any(existing.id == document.id for existing in conversation.documents):
        return
    conversation.documents.append(document)
    if conversation.document_id is None:
        conversation.document_id = document.id
    if conversation.title == DEFAULT_TITLE:
        conversation.title = document.filename[:200]


def associated_documents(conversation: Conversation) -> list[Document]:
    return list(conversation.documents)


def sync_primary_document(conversation: Conversation) -> None:
    ids = [document.id for document in conversation.documents]
    if conversation.document_id not in ids:
        conversation.document_id = ids[0] if ids else None


def history_for_model(messages: list[Message], *, max_chars: int) -> list[dict[str, str]]:
    """Turnos mais recentes que cabem em max_chars, em ordem cronológica."""
    selected: list[tuple[str, str]] = []
    used = 0
    for message in reversed(messages):
        if message.role not in {"user", "assistant"}:
            continue
        content = message.content
        if used + len(content) > max_chars and selected:
            break
        if len(content) > max_chars and not selected:
            content = content[: max(max_chars - 5, 1)].rstrip() + "[...]"
        selected.append((message.role, content))
        used += len(content)
    selected.reverse()
    return [{"role": role, "content": content} for role, content in selected]


def add_turn(
    db: Session,
    conversation: Conversation,
    *,
    question: str,
    answer: str,
    sources: list[ChatSource],
    model: str,
) -> None:
    asked_at = utcnow()
    # A ordem do histórico vem de created_at: a resposta fica sempre depois da pergunta,
    # mesmo quando o relógio do sistema devolve o mesmo instante para as duas.
    answered_at = max(utcnow(), asked_at + timedelta(microseconds=1))
    db.add(
        Message(
            id=str(uuid4()),
            conversation_id=conversation.id,
            role="user",
            content=question,
            created_at=asked_at,
        )
    )
    db.add(
        Message(
            id=str(uuid4()),
            conversation_id=conversation.id,
            role="assistant",
            content=answer,
            sources_json=json.dumps([source.model_dump() for source in sources], ensure_ascii=False),
            model=model[:MODEL_NAME_MAX_CHARS],
            created_at=answered_at,
        )
    )
    conversation.updated_at = answered_at
    db.commit()


def message_count(db: Session, conversation_id: str) -> int:
    return db.scalar(
        select(func.count()).select_from(Message).where(Message.conversation_id == conversation_id)
    ) or 0

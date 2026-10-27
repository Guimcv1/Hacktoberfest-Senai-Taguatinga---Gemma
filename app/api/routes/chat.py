"""Chat sobre um documento do usuário autenticado."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource
from app.services.ai_client import AIClient, AIClientError, AIInvalidResponseError, get_ai_client
from app.services.conversations import (
    ConversationNotFoundError,
    add_turn,
    create_conversation,
    get_owned_conversation,
)
from app.services.document_repo import DocumentNotFoundError, extracted_from_row, get_owned_document
from app.services.retrieval import format_context, retrieve_pages

logger = logging.getLogger("studybuddy")

router = APIRouter(prefix="/api", tags=["chat"])

_MAX_EXCERPT_CHARS = 400


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Perguntar sobre um documento",
)
async def chat(
    payload: ChatRequest,
    settings: Settings = Depends(get_settings),
    ai_client: AIClient = Depends(get_ai_client),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ChatResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A mensagem não pode ser vazia.",
        )
    if len(payload.message) > settings.max_chat_message_chars:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="A mensagem excede o tamanho máximo permitido.",
        )

    try:
        document = get_owned_document(db, current_user.id, payload.document_id)
        if payload.conversation_id:
            conversation = get_owned_conversation(db, current_user.id, payload.conversation_id)
            if conversation.document_id != document.id:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="A conversa não pertence a este documento.",
                )
        else:
            conversation = create_conversation(
                db,
                user_id=current_user.id,
                document_id=document.id,
                title=message[:80],
            )
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from None
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from None

    pages, has_match = retrieve_pages(
        extracted_from_row(document),
        message,
        max_excerpts=settings.max_retrieval_pages,
        max_chars=settings.max_context_chars,
    )
    context = format_context(pages)
    sources = [ChatSource(page=page.page_number, excerpt=_excerpt(page.text)) for page in pages]

    try:
        explanation = await ai_client.generate_explanation(question=message, context=context)
    except AIClientError as exc:
        logger.warning("Falha ao consultar a IA: tipo=%s", type(exc).__name__)
        status_code = (
            status.HTTP_502_BAD_GATEWAY
            if isinstance(exc, AIInvalidResponseError)
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        raise HTTPException(status_code=status_code, detail=exc.public_message) from None

    add_turn(
        db,
        conversation,
        question=message,
        answer=explanation.content,
        sources=sources,
        model=explanation.model,
    )
    logger.info("Chat respondido: document_id=%s pages=%s", document.id, [page.page_number for page in pages])
    return ChatResponse(
        document_id=document.id,
        conversation_id=conversation.id,
        answer=explanation.content,
        sources=sources,
        model=explanation.model,
        status="completed",
        has_relevant_match=has_match,
    )


def _excerpt(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= _MAX_EXCERPT_CHARS:
        return cleaned
    return cleaned[:_MAX_EXCERPT_CHARS].rstrip()

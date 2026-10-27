"""Chat autenticado, com ou sem PDF associado à conversa."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.ai_client import AIClient, AIClientError, AIInvalidResponseError, get_ai_client
from app.services.ai_runtime import get_inference_gate
from app.services.conversations import (
    ConversationNotFoundError,
    add_turn,
    associated_documents,
    create_conversation,
    get_owned_conversation,
    history_for_model,
    link_document,
    sync_primary_document,
)
from app.services.document_repo import DocumentNotFoundError, get_owned_document
from app.services.study_context import document_context

logger = logging.getLogger("studybuddy")

router = APIRouter(prefix="/api", tags=["chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Perguntar ao professor virtual",
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

    user_id = current_user.id
    try:
        conversation = (
            get_owned_conversation(db, user_id, payload.conversation_id) if payload.conversation_id else None
        )
        extra_document = get_owned_document(db, user_id, payload.document_id) if payload.document_id else None
    except (DocumentNotFoundError, ConversationNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from None

    documents = associated_documents(conversation) if conversation is not None else []
    if extra_document is not None and extra_document.id not in {item.id for item in documents}:
        documents.append(extra_document)

    context, has_match, sources = document_context(documents, message, settings)
    history = history_for_model(conversation.messages, max_chars=settings.max_context_chars) if conversation else []
    # Encerra a transação de leitura: a conexão não fica presa ao pool durante a chamada à IA.
    db.commit()

    try:
        async with get_inference_gate().inference():
            explanation = await ai_client.generate_explanation(
                question=message,
                context=context,
                history=history,
                has_relevant_match=has_match,
                has_material=bool(documents),
            )
    except AIClientError as exc:
        logger.warning("Falha ao consultar a IA: tipo=%s", type(exc).__name__)
        status_code = (
            status.HTTP_502_BAD_GATEWAY
            if isinstance(exc, AIInvalidResponseError)
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        raise HTTPException(status_code=status_code, detail=exc.public_message) from None

    try:
        if conversation is None:
            conversation = create_conversation(
                db,
                user_id=user_id,
                document_id=extra_document.id if extra_document is not None else None,
                title=message[:80],
                commit=False,
            )
        elif extra_document is not None:
            link_document(conversation, extra_document)
            sync_primary_document(conversation)
    except (DocumentNotFoundError, ConversationNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from None

    add_turn(
        db,
        conversation,
        question=message,
        answer=explanation.content,
        sources=sources,
        model=explanation.model,
    )
    document_ids = [item.id for item in associated_documents(conversation)] or (
        [extra_document.id] if extra_document is not None else []
    )
    logger.info(
        "Chat respondido: conversation_id=%s documents=%s pages=%s",
        conversation.id,
        document_ids,
        [source.page for source in sources],
    )
    return ChatResponse(
        conversation_id=conversation.id,
        document_id=conversation.document_id,
        document_ids=document_ids,
        answer=explanation.content,
        sources=sources,
        model=explanation.model,
        status="completed",
        has_relevant_match=has_match,
        used_documents=bool(documents),
    )

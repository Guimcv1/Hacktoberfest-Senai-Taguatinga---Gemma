"""Chat sobre um documento previamente enviado."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.schemas.chat import ChatRequest, ChatResponse, ChatSource
from app.services.ai_client import AIClient, AIClientError, AIInvalidResponseError, get_ai_client
from app.services.document_store import DocumentNotFoundError, get_document_store
from app.services.retrieval import format_context, retrieve_relevant_excerpts

logger = logging.getLogger("studybuddy")

router = APIRouter(prefix="/api", tags=["chat"])

_MAX_EXCERPT_CHARS = 400


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Perguntar sobre um documento",
    responses={
        404: {"description": "Documento inexistente ou expirado."},
        422: {"description": "Mensagem vazia ou grande demais."},
        503: {"description": "Serviço de IA indisponível ou em timeout."},
        502: {"description": "Resposta inválida do serviço de IA."},
    },
)
async def chat(
    payload: ChatRequest,
    settings: Settings = Depends(get_settings),
    ai_client: AIClient = Depends(get_ai_client),
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
        stored = get_document_store().get(payload.document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from None

    pages = retrieve_relevant_excerpts(
        stored.as_extracted(),
        message,
        max_excerpts=settings.max_retrieval_pages,
        max_chars=settings.max_context_chars,
    )
    context = format_context(pages)

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

    logger.info(
        "Chat respondido: document_id=%s pages=%s",
        stored.document_id,
        [page.page_number for page in pages],
    )
    return ChatResponse(
        document_id=stored.document_id,
        answer=explanation.content,
        sources=[
            ChatSource(page=page.page_number, excerpt=_excerpt(page.text))
            for page in pages
        ],
        model=explanation.model,
    )


def _excerpt(text: str) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= _MAX_EXCERPT_CHARS:
        return cleaned
    return cleaned[:_MAX_EXCERPT_CHARS].rstrip()

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.questions import (
    GenerateQuestionsRequest,
    QuestionSetListResponse,
    QuestionSetResponse,
)
from app.services.ai_client import AIClient, AIClientError, AIInvalidResponseError, get_ai_client
from app.services.conversations import ConversationNotFoundError
from app.services.questions import (
    InsufficientConversationError,
    generate_question_set,
    list_question_sets,
    question_set_to_response,
)

router = APIRouter(prefix="/api/conversations", tags=["questions"])


@router.post(
    "/{conversation_id}/questions/generate",
    response_model=QuestionSetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Gerar questões a partir da conversa",
    description=(
        "Usa o histórico da conversa e, se houver, os PDFs associados. "
        "A observação é opcional e só personaliza o estilo. "
        "O conjunto gerado é persistido e pode ser relido sem nova inferência."
    ),
)
async def generate_questions(
    conversation_id: str,
    payload: Annotated[GenerateQuestionsRequest | None, Body()] = None,
    settings: Settings = Depends(get_settings),
    ai_client: AIClient = Depends(get_ai_client),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuestionSetResponse:
    body = payload or GenerateQuestionsRequest()
    try:
        row = await generate_question_set(
            db,
            user_id=current_user.id,
            conversation_id=conversation_id,
            payload=body,
            settings=settings,
            ai_client=ai_client,
        )
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from None
    except InsufficientConversationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=exc.message) from None
    except AIClientError as exc:
        status_code = (
            status.HTTP_502_BAD_GATEWAY
            if isinstance(exc, AIInvalidResponseError)
            else status.HTTP_503_SERVICE_UNAVAILABLE
        )
        raise HTTPException(status_code=status_code, detail=exc.public_message) from None
    return question_set_to_response(row)


@router.get(
    "/{conversation_id}/questions",
    response_model=QuestionSetListResponse,
    summary="Listar conjuntos de questões já gerados",
)
def list_generated_questions(
    conversation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuestionSetListResponse:
    try:
        rows, total = list_question_sets(db, current_user.id, conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from None
    return QuestionSetListResponse(items=[question_set_to_response(row) for row in rows], total=total)

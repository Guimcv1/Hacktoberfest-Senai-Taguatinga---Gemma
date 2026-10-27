from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.deps import get_current_user
from app.db.models import User
from app.schemas.ai import UnloadResponse
from app.services.ai_client import AIClient, AIClientError, get_ai_client
from app.services.ai_runtime import (
    AIInferencesInProgressError,
    AIUnloadInProgressError,
    get_inference_gate,
)

logger = logging.getLogger("studybuddy")

router = APIRouter(prefix="/api/ai", tags=["ai"])

_UNLOAD_MESSAGE = (
    "O Ollama aceitou o pedido para descarregar o modelo da memória. "
    "A próxima pergunta pode carregá-lo de novo. "
    "Isso não apaga o modelo nem mede a RAM ou a VRAM liberada."
)


@router.post(
    "/unload",
    response_model=UnloadResponse,
    summary="Descarregar o modelo da memória do Ollama",
    description=(
        "Envia keep_alive=0 ao modelo configurado. Efeito global para quem compartilha "
        "este Ollama. Não interrompe inferências em andamento; nesse caso responde 409. "
        "Não desinstala o modelo nem encerra o Ollama."
    ),
)
async def unload_model(
    _current_user: User = Depends(get_current_user),
    ai_client: AIClient = Depends(get_ai_client),
) -> UnloadResponse:
    gate = get_inference_gate()
    try:
        async with gate.unload():
            await ai_client.unload()
    except (AIInferencesInProgressError, AIUnloadInProgressError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=exc.public_message) from None
    except AIClientError as exc:
        logger.warning("Falha ao descarregar a IA: tipo=%s", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=exc.public_message,
        ) from None
    return UnloadResponse(status="unloaded", model=ai_client.model, message=_UNLOAD_MESSAGE)

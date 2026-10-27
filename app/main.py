import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.chat import router as chat_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings

logger = logging.getLogger("studybuddy")

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description=(
        "Backend da plataforma de estudos StudyBuddy AI: upload de PDFs, "
        "recuperação temporária em memória e chat com o professor virtual."
    ),
    version="0.1.0",
)

app.include_router(health_router)
app.include_router(documents_router)
app.include_router(chat_router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erro interno não tratado.")
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno. Tente novamente mais tarde."},
    )

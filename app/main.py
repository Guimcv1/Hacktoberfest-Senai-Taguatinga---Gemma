import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.middleware import RateLimitMiddleware, RequestIdMiddleware
from app.db.session import init_db

logger = logging.getLogger("studybuddy")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if settings.environment == "production" and "*" in settings.cors_origin_list:
        raise RuntimeError("CORS_ORIGINS não pode ser * em produção.")
    init_db()
    yield


app = FastAPI(
    title="StudyBuddy AI",
    description=(
        "Backend da plataforma de estudos StudyBuddy AI: autenticação, "
        "documentos persistidos por usuário e chat com Gemma 3:4b via Ollama."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(conversations_router)
app.include_router(chat_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": "Dados de entrada inválidos."})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        raise exc
    logger.exception("Erro interno não tratado.")
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno. Tente novamente mais tarde."},
    )

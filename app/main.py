import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.errors import public_validation_errors
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.conversations import router as conversations_router
from app.api.routes.documents import router as documents_router
from app.api.routes.health import router as health_router
from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.core.middleware import (
    BodySizeLimitMiddleware,
    EmptyJsonBodyMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
)
from app.db import session as db_session
from app.db.session import init_db
from app.services.auth import purge_expired_revocations
from app.services.document_repo import purge_expired

logger = logging.getLogger("studybuddy")

settings = get_settings()
configure_logging(settings.log_level)


def purge_expired_data() -> None:
    """Remove documentos vencidos de todos os usuários e revogações de tokens já expirados."""
    assert db_session.SessionLocal is not None
    db = db_session.SessionLocal()
    try:
        removed = purge_expired(db)
        purge_expired_revocations(db)
        if removed:
            logger.info("Documentos vencidos removidos: %s", removed)
    except Exception:
        db.rollback()
        logger.exception("Falha ao remover dados vencidos.")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    purge_expired_data()
    yield


app = FastAPI(
    title="StudyBuddy AI",
    description=(
        "Backend da plataforma de estudos StudyBuddy AI: autenticação, "
        "documentos persistidos por usuário e chat com Gemma 3:4b via Ollama."
    ),
    version="0.3.0",
    lifespan=lifespan,
)

# O último middleware adicionado é o mais externo: CORS envolve inclusive 413, 429 e 500.
app.add_middleware(EmptyJsonBodyMiddleware)
app.add_middleware(BodySizeLimitMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Retry-After"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(conversations_router)
app.include_router(chat_router)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"detail": "Dados de entrada inválidos.", "errors": public_validation_errors(exc.errors())},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Erro interno não tratado.")
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno. Tente novamente mais tarde."},
    )

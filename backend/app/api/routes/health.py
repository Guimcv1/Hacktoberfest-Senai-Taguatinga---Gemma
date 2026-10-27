from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.migrations import head_revision, revision_of_connection
from app.db.session import get_db
from app.schemas.health import HealthResponse, ReadyResponse
from app.services.ai_client import AIClient, get_ai_client

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", service=settings.app_name)


def _database_state(db: Session) -> tuple[str, str]:
    try:
        db.execute(text("SELECT 1"))
        revision = revision_of_connection(db.connection())
    except Exception:
        return "error", "unknown"
    finally:
        db.rollback()
    return "ok", "ok" if revision == head_revision() else "pending"


@router.get(
    "/ready",
    response_model=ReadyResponse,
    responses={503: {"model": ReadyResponse, "description": "Banco indisponível ou migrações pendentes."}},
)
async def ready(
    response: Response,
    check_ai: bool = Query(default=False, description="Também verifica se o Ollama responde (GET /)."),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    ai_client: AIClient = Depends(get_ai_client),
) -> ReadyResponse:
    database, migrations = await run_in_threadpool(_database_state, db)
    ai_configured = bool(settings.ai_base_url)
    ai_state = "not_checked"
    if check_ai:
        if not ai_configured:
            ai_state = "not_configured"
        else:
            ai_state = "ok" if await ai_client.ping() else "unreachable"

    healthy = database == "ok" and migrations == "ok"
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return ReadyResponse(
        status="ok" if healthy else "degraded",
        database=database,
        migrations=migrations,
        ai_configured=ai_configured,
        ai=ai_state,
    )

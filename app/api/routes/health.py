from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.health import HealthResponse, ReadyResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", service=settings.app_name)


@router.get("/ready", response_model=ReadyResponse)
def ready(db: Session = Depends(get_db)) -> ReadyResponse:
    settings = get_settings()
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
        status = "ok"
    except Exception:
        database = "error"
        status = "degraded"
    return ReadyResponse(
        status=status,
        database=database,
        ai_configured=bool(settings.ai_base_url),
    )

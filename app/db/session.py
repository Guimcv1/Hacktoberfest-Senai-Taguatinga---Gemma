from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base

engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def _engine_kwargs(url: str) -> dict:
    kwargs: dict = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in {"sqlite://", "sqlite:///:memory:"}:
            kwargs["poolclass"] = StaticPool
    return kwargs


def configure_engine(url: str | None = None) -> Engine:
    global engine, SessionLocal
    database_url = url or get_settings().database_url
    engine = create_engine(database_url, **_engine_kwargs(database_url))
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return engine


def init_db(url: str | None = None) -> None:
    from app.db import models as _models  # noqa: F401

    database_url = url or get_settings().database_url
    if database_url.startswith("sqlite:///./"):
        Path("data").mkdir(parents=True, exist_ok=True)
    current = configure_engine(database_url)
    Base.metadata.create_all(bind=current)


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        init_db()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

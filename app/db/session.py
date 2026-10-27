import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings

logger = logging.getLogger("studybuddy")

engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def _engine_kwargs(url: str) -> dict:
    # hide_parameters: erros do banco não devem levar e-mails, hashes ou texto de PDFs para os logs.
    kwargs: dict = {"hide_parameters": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if url in {"sqlite://", "sqlite:///:memory:"}:
            kwargs["poolclass"] = StaticPool
    else:
        kwargs["pool_pre_ping"] = True
    return kwargs


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(url: str) -> Engine:
    created = create_engine(url, **_engine_kwargs(url))
    if created.dialect.name == "sqlite":
        event.listen(created, "connect", _enable_sqlite_foreign_keys)
    return created


def configure_engine(url: str | None = None) -> Engine:
    global engine, SessionLocal
    database_url = url or get_settings().database_url
    engine = create_db_engine(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False)
    return engine


def ensure_sqlite_directory(url: str) -> None:
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        return
    database = parsed.database
    if not database or database == ":memory:" or database.startswith("file:"):
        return
    Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)


def init_db(url: str | None = None, *, auto_migrate: bool | None = None) -> Engine:
    from app.db import models as _models  # noqa: F401
    from app.db.migrations import current_revision, head_revision, upgrade_database

    settings = get_settings()
    database_url = url or settings.database_url
    ensure_sqlite_directory(database_url)
    current = configure_engine(database_url)
    should_migrate = settings.db_auto_migrate if auto_migrate is None else auto_migrate
    if should_migrate:
        upgrade_database(current)
    elif current_revision(current) != head_revision():
        logger.warning("Banco fora da revisão mais recente. Execute: alembic upgrade head")
    return current


def get_db() -> Generator[Session, None, None]:
    if SessionLocal is None:
        init_db()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import inspect, text

import app.db.session as db_session
from app.db.base import Base
from app.db.migrations import (
    PROJECT_ROOT,
    MigrationStateError,
    alembic_config,
    current_revision,
    head_revision,
    upgrade_database,
)
from app.db.models import User
from app.db.session import create_db_engine, init_db

APP_TABLES = {
    "users",
    "documents",
    "conversations",
    "conversation_documents",
    "messages",
    "question_sets",
    "revoked_tokens",
}


def _sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _schema_diff(engine) -> list:
    with engine.connect() as connection:
        return compare_metadata(MigrationContext.configure(connection), Base.metadata)


@pytest.fixture
def file_engine(tmp_path: Path):
    engine = create_db_engine(_sqlite_url(tmp_path / "migracao.db"))
    yield engine
    engine.dispose()


def test_upgrade_creates_schema_identical_to_models(file_engine) -> None:
    upgrade_database(file_engine)

    assert current_revision(file_engine) == head_revision()
    assert APP_TABLES <= set(inspect(file_engine).get_table_names())
    assert _schema_diff(file_engine) == []


def test_upgrade_from_002_adds_question_sets(file_engine) -> None:
    config = alembic_config()
    with file_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "002")

    assert "question_sets" not in inspect(file_engine).get_table_names()
    upgrade_database(file_engine)
    assert "question_sets" in inspect(file_engine).get_table_names()
    assert current_revision(file_engine) == head_revision()
    assert _schema_diff(file_engine) == []


def test_upgrade_is_idempotent(file_engine) -> None:
    upgrade_database(file_engine)
    upgrade_database(file_engine)

    assert current_revision(file_engine) == head_revision()


def test_legacy_create_all_database_is_stamped_and_keeps_data(file_engine) -> None:
    Base.metadata.create_all(bind=file_engine)
    with file_engine.begin() as connection:
        connection.execute(
            User.__table__.insert().values(
                id="legado",
                email="legado@example.com",
                password_hash="hash",
                name="Legado",
                created_at=datetime.now(timezone.utc),
            )
        )

    upgrade_database(file_engine)

    assert current_revision(file_engine) == head_revision()
    with file_engine.connect() as connection:
        assert connection.execute(text("SELECT email FROM users")).scalar_one() == "legado@example.com"
    assert _schema_diff(file_engine) == []


def test_partial_schema_without_history_is_not_touched(file_engine) -> None:
    User.__table__.create(bind=file_engine)

    with pytest.raises(MigrationStateError):
        upgrade_database(file_engine)

    assert set(inspect(file_engine).get_table_names()) == {"users"}


def test_downgrade_to_base_and_upgrade_again(file_engine) -> None:
    upgrade_database(file_engine)
    config = alembic_config()
    with file_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")

    assert not APP_TABLES & set(inspect(file_engine).get_table_names())

    upgrade_database(file_engine)
    assert current_revision(file_engine) == head_revision()


def test_init_db_applies_migrations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_session, "engine", db_session.engine)
    monkeypatch.setattr(db_session, "SessionLocal", db_session.SessionLocal)
    url = _sqlite_url(tmp_path / "subpasta" / "api.db")

    engine = init_db(url, auto_migrate=True)
    try:
        assert current_revision(engine) == head_revision()
    finally:
        engine.dispose()


def test_init_db_without_auto_migrate_leaves_schema_alone(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db_session, "engine", db_session.engine)
    monkeypatch.setattr(db_session, "SessionLocal", db_session.SessionLocal)

    engine = init_db(_sqlite_url(tmp_path / "manual.db"), auto_migrate=False)
    try:
        assert inspect(engine).get_table_names() == []
    finally:
        engine.dispose()


def test_alembic_cli_upgrades_without_api_secrets(tmp_path: Path) -> None:
    env = {key: value for key, value in os.environ.items() if key != "JWT_SECRET"}
    env.update({"APP_ENV_FILE": "", "DATABASE_URL": _sqlite_url(tmp_path / "nova" / "cli.db")})

    def alembic(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "alembic", *args],
            cwd=PROJECT_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )

    upgraded = alembic("upgrade", "head")
    assert upgraded.returncode == 0, upgraded.stderr
    current = alembic("current")
    assert current.returncode == 0, current.stderr
    assert f"{head_revision()} (head)" in current.stdout


def test_migrations_on_configured_test_database() -> None:
    """Na CI com PostgreSQL, valida a migração no banco real configurado."""
    engine = db_session.engine
    assert engine is not None
    Base.metadata.drop_all(bind=engine)
    with engine.begin() as connection:
        connection.execute(text("DROP TABLE IF EXISTS alembic_version"))

    upgrade_database(engine)

    assert current_revision(engine) == head_revision()
    assert _schema_diff(engine) == []

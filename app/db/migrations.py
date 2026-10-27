"""Migrações Alembic aplicadas pela API e pelos testes."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.engine import Connection, Engine

logger = logging.getLogger("studybuddy")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BASELINE_REVISION = "001"
# Tabelas criadas pelo antigo Base.metadata.create_all, idênticas à revisão 001.
_BASELINE_TABLES = frozenset({"users", "documents", "conversations", "messages", "revoked_tokens"})


class MigrationStateError(RuntimeError):
    pass


def alembic_config() -> Config:
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    return config


@lru_cache(maxsize=1)
def head_revision() -> str | None:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def revision_of_connection(connection: Connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()


def current_revision(engine: Engine) -> str | None:
    with engine.connect() as connection:
        return revision_of_connection(connection)


def upgrade_database(engine: Engine) -> None:
    """Leva o banco até a revisão mais recente sem apagar dados.

    Bancos criados pelo create_all de versões anteriores não têm alembic_version;
    eles são carimbados na revisão inicial antes do upgrade.
    """
    config = alembic_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())
        if "alembic_version" not in tables:
            existing = _BASELINE_TABLES & tables
            if existing == _BASELINE_TABLES:
                logger.warning(
                    "Banco sem histórico de migrações; registrando a revisão inicial %s.",
                    BASELINE_REVISION,
                )
                command.stamp(config, BASELINE_REVISION)
            elif existing:
                raise MigrationStateError(
                    "O banco tem apenas parte das tabelas do StudyBuddy e nenhum histórico de "
                    f"migrações ({', '.join(sorted(existing))}). Verifique-o manualmente antes de migrar."
                )
        command.upgrade(config, "head")

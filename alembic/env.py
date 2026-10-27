from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_database_url
from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.session import ensure_sqlite_directory

config = context.config
shared_connection = config.attributes.get("connection")

# Quando a API executa as migrações, a configuração de logs da aplicação é preservada.
if config.config_file_name is not None and shared_connection is None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _configure(**kwargs) -> None:
    context.configure(target_metadata=target_metadata, compare_type=True, **kwargs)


def run_migrations_offline() -> None:
    _configure(url=get_database_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run_with(connection) -> None:
    _configure(connection=connection, render_as_batch=connection.dialect.name == "sqlite")
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if shared_connection is not None:
        _run_with(shared_connection)
        return

    url = get_database_url()
    ensure_sqlite_directory(url)
    connectable = create_engine(url, poolclass=pool.NullPool)
    try:
        with connectable.connect() as connection:
            _run_with(connection)
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

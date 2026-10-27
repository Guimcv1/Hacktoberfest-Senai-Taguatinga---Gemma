from __future__ import annotations

import os
from collections.abc import Iterator

os.environ.update(
    {
        "APP_ENV_FILE": "",
        "ENVIRONMENT": "test",
        "JWT_SECRET": "test-jwt-secret-key-with-at-least-32-chars",
        "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", "sqlite://"),
        "AI_BASE_URL": "",
        "RATE_LIMIT_PER_MINUTE": "0",
        "RATE_LIMIT_AUTH_PER_MINUTE": "0",
        "CORS_ORIGINS": "http://localhost:5173,http://testserver",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import make_url, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

import app.db.session as db_session  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db import models as _models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.db.migrations import upgrade_database  # noqa: E402
from app.main import app  # noqa: E402
from app.services.ai_client import get_ai_client  # noqa: E402
from app.services.ai_runtime import get_inference_gate  # noqa: E402
from tests.helpers import register_and_login  # noqa: E402

if "test" not in (make_url(os.environ["DATABASE_URL"]).database or "test"):
    raise RuntimeError("TEST_DATABASE_URL deve apontar para um banco descartável com 'test' no nome.")

get_settings.cache_clear()
engine = db_session.configure_engine(os.environ["DATABASE_URL"])
# O esquema dos testes vem das migrações, como em produção, e não de create_all.
Base.metadata.drop_all(bind=engine)
with engine.begin() as _connection:
    _connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
upgrade_database(engine)


def _clear_tables() -> None:
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


class _BlockedAIClient:
    async def generate_explanation(self, **kwargs):
        raise AssertionError("Os testes não devem chamar o serviço real de IA.")

    async def generate_completion(self, **kwargs):
        raise AssertionError("Os testes não devem chamar o serviço real de IA.")

    async def unload(self, **kwargs):
        raise AssertionError("Os testes não devem chamar o serviço real de IA.")

    async def ping(self, **kwargs):
        raise AssertionError("Os testes não devem chamar o serviço real de IA.")


@pytest.fixture(autouse=True)
def reset_runtime_state() -> Iterator[None]:
    _clear_tables()
    get_inference_gate().reset()
    app.dependency_overrides.clear()
    app.dependency_overrides[get_ai_client] = lambda: _BlockedAIClient()
    yield
    get_inference_gate().reset()
    app.dependency_overrides.clear()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def db_session_factory():
    assert db_session.SessionLocal is not None
    return db_session.SessionLocal


@pytest.fixture
def db(db_session_factory) -> Iterator[Session]:
    session = db_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    return register_and_login(client, "aluno@example.com")

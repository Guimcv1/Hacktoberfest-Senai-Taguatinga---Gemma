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
from sqlalchemy.orm import Session  # noqa: E402

import app.db.session as db_session  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db import models as _models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.services.ai_client import get_ai_client  # noqa: E402
from tests.helpers import register_and_login  # noqa: E402

get_settings.cache_clear()
engine = db_session.configure_engine(os.environ["DATABASE_URL"])


class _BlockedAIClient:
    async def generate_explanation(self, **kwargs):
        raise AssertionError("Os testes não devem chamar o serviço real de IA.")


@pytest.fixture(autouse=True)
def reset_runtime_state() -> Iterator[None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides.clear()
    app.dependency_overrides[get_ai_client] = lambda: _BlockedAIClient()
    yield
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

from __future__ import annotations

import os
from collections.abc import Iterator

os.environ["JWT_SECRET"] = "test-jwt-secret-key-32-chars-minimum"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ENVIRONMENT"] = "test"
os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"
os.environ["CORS_ORIGINS"] = "http://localhost:5173,http://testserver"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, configure_engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.ai_client import get_ai_client  # noqa: E402

get_settings.cache_clear()
engine = configure_engine("sqlite://")
Base.metadata.create_all(bind=engine)


class _BlockedAIClient:
    async def generate_explanation(self, **kwargs):
        raise AssertionError("Os testes não devem chamar o serviço real de IA.")


def _override_db() -> Iterator[Session]:
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_db


def _auth_headers(client: TestClient, email: str, password: str = "senha1234", name: str = "Estudante") -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "name": name},
    )
    if response.status_code == 409:
        response = client.post("/api/auth/login", json={"email": email, "password": password})
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def reset_runtime_state() -> Iterator[None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app.dependency_overrides[get_ai_client] = lambda: _BlockedAIClient()
    yield
    app.dependency_overrides.pop(get_ai_client, None)
    app.dependency_overrides.pop(get_settings, None)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    return _auth_headers(client, "aluno@example.com")

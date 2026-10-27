from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_client import get_ai_client
from app.services.document_store import get_document_store


class _BlockedAIClient:
    async def generate_explanation(self, **kwargs):
        raise AssertionError("Os testes não devem chamar o serviço real de IA.")


@pytest.fixture(autouse=True)
def reset_runtime_state() -> Iterator[None]:
    store = get_document_store()
    store.clear()
    app.dependency_overrides[get_ai_client] = lambda: _BlockedAIClient()
    yield
    store.clear()
    app.dependency_overrides.pop(get_ai_client, None)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)

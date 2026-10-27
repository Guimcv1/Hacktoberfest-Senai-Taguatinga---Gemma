from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_client import AITimeoutError, AIUnavailableError, get_ai_client
from app.services.ai_runtime import get_inference_gate
from tests.fakes import FakeAIClient

UNLOAD_URL = "/api/ai/unload"


def _enable_fake(**kwargs) -> FakeAIClient:
    fake = FakeAIClient(**kwargs)
    app.dependency_overrides[get_ai_client] = lambda: fake
    return fake


def test_unload_requires_authentication(client: TestClient) -> None:
    response = client.post(UNLOAD_URL)
    assert response.status_code == 401


def test_unload_asks_ollama_and_returns_clear_success(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    fake = _enable_fake()

    response = client.post(UNLOAD_URL, headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "unloaded"
    assert body["model"] == "gemma4:e4b"
    assert fake.unload_calls == 1
    assert "RAM" in body["message"] or "memória" in body["message"].lower()
    lowered = body["message"].lower()
    assert "não apaga" in lowered or "nao apaga" in lowered
    assert "mede" in lowered


def test_unload_conflict_when_inferences_are_running(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    _enable_fake()
    get_inference_gate()._in_flight = 1

    response = client.post(UNLOAD_URL, headers=auth_headers)

    assert response.status_code == 409
    assert "andamento" in response.json()["detail"].lower()
    assert get_inference_gate().unloading is False


def test_chat_is_blocked_while_unload_runs(client: TestClient, auth_headers: dict[str, str]) -> None:
    _enable_fake()
    get_inference_gate()._unloading = True

    response = client.post("/api/chat", headers=auth_headers, json={"message": "O que e mitose?"})

    assert response.status_code == 503
    assert "descarreg" in response.json()["detail"].lower()


def test_unload_timeout_returns_503_without_internals(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    fake = _enable_fake(unload_error=AITimeoutError())

    response = client.post(UNLOAD_URL, headers=auth_headers)

    assert response.status_code == 503
    assert "demorou" in response.json()["detail"]
    assert "11434" not in response.text
    assert "ai.test" not in response.text
    assert fake.unload_calls == 1
    assert get_inference_gate().unloading is False


def test_unload_ollama_error_is_not_treated_as_success(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    _enable_fake(unload_error=AIUnavailableError())

    response = client.post(UNLOAD_URL, headers=auth_headers)

    assert response.status_code == 503
    assert response.json().get("status") != "unloaded"


def test_api_does_not_install_or_delete_models() -> None:
    root = Path(__file__).resolve().parents[1]
    sources = [
        (root / "app" / "main.py").read_text(encoding="utf-8"),
        (root / "app" / "services" / "ai_client.py").read_text(encoding="utf-8"),
        (root / "app" / "api" / "routes" / "ai.py").read_text(encoding="utf-8"),
    ]
    joined = "\n".join(sources)
    for token in ('"/api/pull"', "'/api/pull'", '"/api/delete"', "'/api/delete'", '"/api/stop"', "'/api/stop'"):
        assert token not in joined
    assert "ollama rm" not in joined
    assert "ollama pull" not in joined


def test_openapi_documents_unload() -> None:
    schema = app.openapi()
    assert "/api/ai/unload" in schema["paths"]
    operation = schema["paths"]["/api/ai/unload"]["post"]
    assert operation.get("security")
    assert "204" not in (operation.get("responses") or {})


def test_question_generation_blocked_during_unload(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    conversation = client.post("/api/conversations", headers=auth_headers, json={})
    assert conversation.status_code == 201
    conversation_id = conversation.json()["id"]
    _enable_fake(content="Explicacao persistida no historico")
    asked = client.post(
        "/api/chat",
        headers=auth_headers,
        json={
            "conversation_id": conversation_id,
            "message": "Explique com detalhes o que e mitose, para que serve e como se diferencia da meiose.",
        },
    )
    assert asked.status_code == 200, asked.text
    get_inference_gate()._unloading = True

    response = client.post(
        f"/api/conversations/{conversation_id}/questions/generate",
        headers=auth_headers,
        json={},
    )

    assert response.status_code == 503
    assert "descarreg" in response.json()["detail"].lower()

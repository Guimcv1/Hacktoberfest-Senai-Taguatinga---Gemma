from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_client import get_ai_client
from app.services.document_repo import expire_document
from tests.fakes import FakeAIClient
from tests.helpers import build_pdf


def _upload(client: TestClient, auth_headers: dict[str, str]) -> str:
    response = client.post(
        "/api/documents",
        files={"file": ("aula.pdf", build_pdf(["A mitose divide celulas"]), "application/pdf")},
        headers=auth_headers,
    )
    return response.json()["document_id"]


def test_conversation_history_survives_model_keep_alive_expiry(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    """O keep_alive descarrega o Gemma no Ollama; o histórico fica no banco da API."""
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient("Explicacao persistida")
    document_id = _upload(client, auth_headers)
    conversation_id = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"document_id": document_id, "message": "Explique a mitose"},
    ).json()["conversation_id"]

    # Simula o fim do keep_alive: um cliente novo, sem estado de modelo na API.
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient("Ainda no historico")

    detail = client.get(f"/api/conversations/{conversation_id}", headers=auth_headers)
    listed = client.get("/api/conversations", headers=auth_headers)

    assert detail.status_code == 200
    assert [message["role"] for message in detail.json()["messages"]] == ["user", "assistant"]
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == conversation_id


def test_conversation_history_persists(client: TestClient, auth_headers: dict[str, str]) -> None:
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient("Explicacao persistida")
    document_id = _upload(client, auth_headers)
    chat = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"document_id": document_id, "message": "Explique a mitose"},
    )
    assert chat.status_code == 200
    conversation_id = chat.json()["conversation_id"]

    detail = client.get(f"/api/conversations/{conversation_id}", headers=auth_headers)
    assert detail.status_code == 200
    messages = detail.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["sources"][0]["page"] == 1


def test_delete_conversation(client: TestClient, auth_headers: dict[str, str]) -> None:
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient("ok")
    document_id = _upload(client, auth_headers)
    conversation_id = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"document_id": document_id, "message": "Explique"},
    ).json()["conversation_id"]

    deleted = client.delete(f"/api/conversations/{conversation_id}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/conversations/{conversation_id}", headers=auth_headers).status_code == 404


def test_conversations_survive_expired_documents(
    client: TestClient, auth_headers: dict[str, str], db
) -> None:
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient("ok")
    document_id = _upload(client, auth_headers)
    client.post("/api/chat", headers=auth_headers, json={"document_id": document_id, "message": "Explique"})
    listed = client.get("/api/conversations", headers=auth_headers).json()
    assert listed["total"] == 1
    conversation_id = listed["items"][0]["id"]

    expire_document(db, document_id)

    after = client.get("/api/conversations", headers=auth_headers).json()
    assert after["total"] == 1
    assert after["items"][0]["id"] == conversation_id
    assert after["items"][0]["document_ids"] == []
    detail = client.get(f"/api/conversations/{conversation_id}", headers=auth_headers).json()
    assert len(detail["messages"]) == 2


def test_create_conversation_without_document(client: TestClient, auth_headers: dict[str, str]) -> None:
    created = client.post("/api/conversations", headers=auth_headers, json={})

    assert created.status_code == 201
    payload = created.json()
    assert payload["document_id"] is None
    assert payload["document_ids"] == []
    assert payload["message_count"] == 0
    assert payload["title"] == "Nova conversa"


def test_attach_uploaded_pdf_to_existing_conversation(client: TestClient, auth_headers: dict[str, str]) -> None:
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient("ok")
    conversation_id = client.post("/api/conversations", headers=auth_headers, json={}).json()["id"]
    document_id = _upload(client, auth_headers)

    attached = client.post(
        f"/api/conversations/{conversation_id}/documents",
        headers=auth_headers,
        json={"document_id": document_id},
    )
    chat = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"conversation_id": conversation_id, "message": "Explique a mitose"},
    )

    assert attached.status_code == 200
    assert attached.json()["document_ids"] == [document_id]
    assert chat.status_code == 200
    assert chat.json()["has_relevant_match"] is True
    assert chat.json()["sources"][0]["page"] == 1
    assert chat.json()["sources"][0]["document_id"] == document_id


def test_upload_can_attach_to_conversation(client: TestClient, auth_headers: dict[str, str]) -> None:
    conversation_id = client.post("/api/conversations", headers=auth_headers, json={}).json()["id"]
    response = client.post(
        "/api/documents",
        headers=auth_headers,
        files={"file": ("aula.pdf", build_pdf(["A mitose divide celulas"]), "application/pdf")},
        data={"conversation_id": conversation_id},
    )

    assert response.status_code == 201
    assert response.json()["conversation_id"] == conversation_id
    detail = client.get(f"/api/conversations/{conversation_id}", headers=auth_headers).json()
    assert detail["document_ids"] == [response.json()["document_id"]]


def test_delete_document(client: TestClient, auth_headers: dict[str, str]) -> None:
    document_id = _upload(client, auth_headers)
    assert client.delete(f"/api/documents/{document_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/documents/{document_id}", headers=auth_headers).status_code == 404

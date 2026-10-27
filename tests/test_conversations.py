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


def test_conversations_of_expired_documents_leave_the_listing(
    client: TestClient, auth_headers: dict[str, str], db
) -> None:
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient("ok")
    document_id = _upload(client, auth_headers)
    client.post("/api/chat", headers=auth_headers, json={"document_id": document_id, "message": "Explique"})
    assert client.get("/api/conversations", headers=auth_headers).json()["total"] == 1

    expire_document(db, document_id)

    assert client.get("/api/conversations", headers=auth_headers).json()["total"] == 0


def test_delete_document(client: TestClient, auth_headers: dict[str, str]) -> None:
    document_id = _upload(client, auth_headers)
    assert client.delete(f"/api/documents/{document_id}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/documents/{document_id}", headers=auth_headers).status_code == 404

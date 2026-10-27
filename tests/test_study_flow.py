"""Fluxo completo: conversa sem PDF → chat → upload independente → associação → chat com material."""

from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_client import get_ai_client
from tests.fakes import FakeAIClient
from tests.helpers import build_pdf, register_and_login


def _enable_ai() -> FakeAIClient:
    fake = FakeAIClient("Resposta do professor")
    app.dependency_overrides[get_ai_client] = lambda: fake
    return fake


def test_complete_flow_create_chat_upload_then_attach(client: TestClient, auth_headers: dict[str, str]) -> None:
    fake = _enable_ai()

    created = client.post("/api/conversations", headers=auth_headers)
    assert created.status_code == 201, created.text
    conversation_id = created.json()["id"]
    assert created.json()["document_id"] is None
    assert created.json()["document_ids"] == []

    asked = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"conversation_id": conversation_id, "message": "O que e mitose?"},
    )
    assert asked.status_code == 200, asked.text
    assert asked.json()["used_documents"] is False
    assert asked.json()["sources"] == []
    assert fake.last_call["has_material"] is False

    uploaded = client.post(
        "/api/documents",
        headers=auth_headers,
        files={"file": ("aula.pdf", build_pdf(["A mitose divide celulas."]), "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["conversation_id"] is None
    document_id = uploaded.json()["document_id"]
    assert client.get("/api/conversations", headers=auth_headers).json()["total"] == 1

    attached = client.post(
        f"/api/conversations/{conversation_id}/documents",
        headers=auth_headers,
        json={"document_id": document_id},
    )
    assert attached.status_code == 200, attached.text
    assert attached.json()["document_ids"] == [document_id]

    with_pdf = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"conversation_id": conversation_id, "message": "Explique a mitose"},
    )
    assert with_pdf.status_code == 200, with_pdf.text
    assert with_pdf.json()["used_documents"] is True
    assert with_pdf.json()["has_relevant_match"] is True
    assert with_pdf.json()["sources"][0]["page"] == 1
    assert with_pdf.json()["sources"][0]["document_id"] == document_id
    assert "mitose" in fake.last_call["context"].lower()
    assert fake.last_call["history"][0]["content"] == "O que e mitose?"


def test_upload_and_conversation_creation_do_not_require_each_other(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    _enable_ai()
    uploaded = client.post(
        "/api/documents",
        headers=auth_headers,
        files={"file": ("aula.pdf", build_pdf(["Texto isolado"]), "application/pdf")},
    )
    created = client.post("/api/conversations", headers=auth_headers, json={"document_id": None})

    assert uploaded.status_code == 201
    assert created.status_code == 201
    assert uploaded.json()["conversation_id"] is None
    assert created.json()["document_ids"] == []
    assert client.get("/api/conversations", headers=auth_headers).json()["total"] == 1
    assert client.get("/api/documents", headers=auth_headers).json()["total"] == 1


def test_create_conversation_accepts_empty_json_bodies(client: TestClient, auth_headers: dict[str, str]) -> None:
    missing_body = client.post("/api/conversations", headers=auth_headers)
    empty_json = client.post(
        "/api/conversations",
        headers={**auth_headers, "Content-Type": "application/json"},
        content=b"",
    )
    null_body = client.post(
        "/api/conversations",
        headers={**auth_headers, "Content-Type": "application/json"},
        content=b"null",
    )
    blank_id = client.post("/api/conversations", headers=auth_headers, json={"document_id": ""})

    assert missing_body.status_code == 201, missing_body.text
    assert empty_json.status_code == 201, empty_json.text
    assert null_body.status_code == 201, null_body.text
    assert blank_id.status_code == 201, blank_id.text
    assert all(item.json()["document_ids"] == [] for item in (missing_body, empty_json, null_body, blank_id))


def test_upload_ignores_blank_conversation_id(client: TestClient, auth_headers: dict[str, str]) -> None:
    response = client.post(
        "/api/documents",
        headers=auth_headers,
        files={"file": ("aula.pdf", build_pdf(["Conteudo"]), "application/pdf")},
        data={"conversation_id": "undefined"},
    )

    assert response.status_code == 201, response.text
    assert response.json()["conversation_id"] is None
    assert client.get("/api/conversations", headers=auth_headers).json()["total"] == 0


def test_cannot_attach_another_users_document_in_study_flow(client: TestClient) -> None:
    _enable_ai()
    alice = register_and_login(client, "alice-flow@example.com")
    bob = register_and_login(client, "bob-flow@example.com")
    alice_doc = client.post(
        "/api/documents",
        headers=alice,
        files={"file": ("aula.pdf", build_pdf(["Segredo"]), "application/pdf")},
    ).json()["document_id"]
    bob_conversation = client.post("/api/conversations", headers=bob).json()["id"]

    attached = client.post(
        f"/api/conversations/{bob_conversation}/documents",
        headers=bob,
        json={"document_id": alice_doc},
    )
    uploaded_to_bob = client.post(
        "/api/documents",
        headers=bob,
        files={"file": ("outro.pdf", build_pdf(["Material do Bob"]), "application/pdf")},
        data={"conversation_id": bob_conversation},
    )

    assert attached.status_code == 404
    assert uploaded_to_bob.status_code == 201
    assert client.get(f"/api/conversations/{bob_conversation}", headers=bob).json()["document_ids"] == [
        uploaded_to_bob.json()["document_id"]
    ]
    assert alice_doc not in client.get(f"/api/conversations/{bob_conversation}", headers=bob).json()["document_ids"]

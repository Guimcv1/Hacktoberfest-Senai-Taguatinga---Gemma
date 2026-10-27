from fastapi.testclient import TestClient

from tests.helpers import build_pdf, register_and_login


def test_user_cannot_access_another_users_document(client: TestClient) -> None:
    alice = register_and_login(client, "alice@example.com")
    bob = register_and_login(client, "bob@example.com")
    uploaded = client.post(
        "/api/documents",
        files={"file": ("alice.pdf", build_pdf(["Segredo da Alice"]), "application/pdf")},
        headers=alice,
    )
    document_id = uploaded.json()["document_id"]

    assert client.get(f"/api/documents/{document_id}", headers=bob).status_code == 404
    assert client.delete(f"/api/documents/{document_id}", headers=bob).status_code == 404
    chat = client.post(
        "/api/chat",
        headers=bob,
        json={"document_id": document_id, "message": "Qual e o segredo?"},
    )
    assert chat.status_code == 404


def test_list_only_returns_own_documents(client: TestClient) -> None:
    alice = register_and_login(client, "alice2@example.com")
    bob = register_and_login(client, "bob2@example.com")
    client.post(
        "/api/documents",
        files={"file": ("a.pdf", build_pdf(["Material da Alice"]), "application/pdf")},
        headers=alice,
    )
    listed = client.get("/api/documents", headers=bob)
    assert listed.status_code == 200
    assert listed.json()["total"] == 0

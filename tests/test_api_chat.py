from fastapi.testclient import TestClient

from app.main import app
from app.services.ai_client import get_ai_client
from app.services.document_repo import expire_document
from app.db.session import SessionLocal
from tests.fakes import FakeAIClient
from tests.helpers import build_pdf

CHAT_URL = "/api/chat"
UPLOAD_URL = "/api/documents"


def _upload(client: TestClient, pages: list[str], auth_headers: dict[str, str], filename: str = "material.pdf") -> dict:
    response = client.post(
        UPLOAD_URL,
        files={"file": (filename, build_pdf(pages), "application/pdf")},
        headers=auth_headers,
    )
    assert response.status_code == 201
    return response.json()


def _enable_fake_ai(content: str = "Resposta mockada do professor") -> FakeAIClient:
    fake = FakeAIClient(content=content, model="gemma3:4b")
    app.dependency_overrides[get_ai_client] = lambda: fake
    return fake


def test_upload_then_retrieve_document_by_id(client: TestClient, auth_headers: dict[str, str]) -> None:
    payload = _upload(client, ["Conteudo da pagina 1", "Conteudo da pagina 2"], auth_headers)

    stored = client.get(f"/api/documents/{payload['document_id']}", headers=auth_headers)

    assert stored.status_code == 200
    body = stored.json()
    assert body["document_id"] == payload["document_id"]
    assert body["filename"] == "material.pdf"
    assert body["page_count"] == 2
    assert body["pages"][1]["page_number"] == 2


def test_chat_with_valid_document_returns_mocked_answer(client: TestClient, auth_headers: dict[str, str]) -> None:
    fake = _enable_fake_ai("Mitose e o processo de divisao celular.")
    uploaded = _upload(
        client,
        [
            "Introducao ao caderno de biologia.",
            "A mitose e um processo de divisao celular.",
            "Referencias finais do material.",
        ],
        auth_headers,
    )

    response = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": uploaded["document_id"], "message": "Explique a mitose deste capitulo"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] == uploaded["document_id"]
    assert payload["answer"] == "Mitose e o processo de divisao celular."
    assert payload["model"] == "gemma3:4b"
    assert payload["status"] == "completed"
    assert payload["sources"][0]["page"] == 2
    assert "mitose" in payload["sources"][0]["excerpt"].lower()
    assert fake.calls == 1
    assert fake.last_call is not None
    assert "Explique a mitose deste capitulo" in fake.last_call["question"]
    assert "[Página 2]" in fake.last_call["context"]


def test_chat_sources_use_retrieved_page_numbers_not_model_text(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    _enable_fake_ai("Veja a pagina 99 do livro inventado.")
    uploaded = _upload(client, ["Texto irrelevante", "A fotossintese ocorre nos cloroplastos."], auth_headers)

    payload = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": uploaded["document_id"], "message": "Onde ocorre a fotossintese?"},
    ).json()

    assert [source["page"] for source in payload["sources"]] == [2]
    assert all(source["page"] != 99 for source in payload["sources"])


def test_chat_unknown_document_returns_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    _enable_fake_ai()
    response = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": "00000000-0000-0000-0000-000000000000", "message": "O que e isso?"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Documento não encontrado ou expirado."


def test_chat_expired_document_returns_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    _enable_fake_ai()
    uploaded = _upload(client, ["Conteudo temporario"], auth_headers)
    db = SessionLocal()
    try:
        expire_document(db, uploaded["document_id"])
    finally:
        db.close()

    response = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": uploaded["document_id"], "message": "Resuma o texto"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Documento não encontrado ou expirado."


def test_chat_rejects_empty_message(client: TestClient, auth_headers: dict[str, str]) -> None:
    _enable_fake_ai()
    uploaded = _upload(client, ["Conteudo"], auth_headers)

    empty = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": uploaded["document_id"], "message": ""},
    )
    blank = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": uploaded["document_id"], "message": "   "},
    )

    assert empty.status_code == 422
    assert blank.status_code == 422


def test_chat_rejects_oversized_message(client: TestClient, auth_headers: dict[str, str]) -> None:
    _enable_fake_ai()
    uploaded = _upload(client, ["Conteudo"], auth_headers)

    response = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": uploaded["document_id"], "message": "x" * 2001},
    )

    assert response.status_code == 422
    assert "tamanho máximo" in response.json()["detail"]


def test_chat_timeout_returns_503(client: TestClient, auth_headers: dict[str, str]) -> None:
    class TimeoutAI:
        async def generate_explanation(self, **kwargs):
            from app.services.ai_client import AITimeoutError

            raise AITimeoutError()

    app.dependency_overrides[get_ai_client] = lambda: TimeoutAI()
    uploaded = _upload(client, ["Conteudo"], auth_headers)

    response = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": uploaded["document_id"], "message": "Explique o conteudo"},
    )

    assert response.status_code == 503
    assert "demorou" in response.json()["detail"]
    assert "trycloudflare" not in response.json()["detail"]


def test_chat_invalid_ai_response_returns_502(client: TestClient, auth_headers: dict[str, str]) -> None:
    class InvalidAI:
        async def generate_explanation(self, **kwargs):
            from app.services.ai_client import AIInvalidResponseError

            raise AIInvalidResponseError()

    app.dependency_overrides[get_ai_client] = lambda: InvalidAI()
    uploaded = _upload(client, ["Conteudo"], auth_headers)

    response = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": uploaded["document_id"], "message": "Explique o conteudo"},
    )

    assert response.status_code == 502
    assert "válida" in response.json()["detail"]

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.services.ai_client import get_ai_client
from app.services.document_repo import expire_document
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
    assert fake.last_call["has_material"] is True


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


def test_chat_expired_document_returns_404(
    client: TestClient, auth_headers: dict[str, str], db: Session
) -> None:
    _enable_fake_ai()
    uploaded = _upload(client, ["Conteudo temporario"], auth_headers)
    expire_document(db, uploaded["document_id"])

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


def test_ai_failure_does_not_leave_an_empty_conversation(client: TestClient, auth_headers: dict[str, str]) -> None:
    class TimeoutAI:
        async def generate_explanation(self, **kwargs):
            from app.services.ai_client import AITimeoutError

            raise AITimeoutError()

    app.dependency_overrides[get_ai_client] = lambda: TimeoutAI()
    uploaded = _upload(client, ["Conteudo"], auth_headers)

    response = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": uploaded["document_id"], "message": "Explique"},
    )

    assert response.status_code == 503
    assert client.get("/api/conversations", headers=auth_headers).json()["total"] == 0


def test_follow_up_reuses_conversation_and_keeps_order(client: TestClient, auth_headers: dict[str, str]) -> None:
    _enable_fake_ai("Resposta")
    uploaded = _upload(client, ["A mitose divide celulas."], auth_headers)
    first = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": uploaded["document_id"], "message": "O que e mitose?"},
    ).json()

    second = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={
            "document_id": uploaded["document_id"],
            "conversation_id": first["conversation_id"],
            "message": "E as celulas?",
        },
    )

    assert second.status_code == 200
    assert second.json()["conversation_id"] == first["conversation_id"]
    detail = client.get(f"/api/conversations/{first['conversation_id']}", headers=auth_headers).json()
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant", "user", "assistant"]
    assert detail["messages"][2]["content"] == "E as celulas?"
    assert client.get("/api/conversations", headers=auth_headers).json()["total"] == 1


def test_chat_can_attach_a_second_owned_document(client: TestClient, auth_headers: dict[str, str]) -> None:
    _enable_fake_ai()
    first_doc = _upload(client, ["Documento A"], auth_headers)
    second_doc = _upload(client, ["Documento B sobre mitose"], auth_headers)
    conversation_id = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": first_doc["document_id"], "message": "Explique"},
    ).json()["conversation_id"]

    response = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": second_doc["document_id"], "conversation_id": conversation_id, "message": "Explique a mitose"},
    )

    assert response.status_code == 200
    assert set(response.json()["document_ids"]) == {first_doc["document_id"], second_doc["document_id"]}


def test_unknown_conversation_returns_404(client: TestClient, auth_headers: dict[str, str]) -> None:
    fake = _enable_fake_ai()
    uploaded = _upload(client, ["Conteudo"], auth_headers)

    response = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": uploaded["document_id"], "conversation_id": "inexistente", "message": "Explique"},
    )

    assert response.status_code == 404
    assert fake.calls == 0


def test_source_excerpt_comes_from_the_matching_part_of_a_long_page(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    _enable_fake_ai()
    long_line = "Texto de abertura sem relacao com a pergunta. " * 2
    pages = [long_line] * 8 + ["O ribossomo sintetiza proteinas."]
    uploaded = _upload(client, ["\n".join(pages)], auth_headers)

    payload = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": uploaded["document_id"], "message": "O que faz o ribossomo?"},
    ).json()

    assert "ribossomo" in payload["sources"][0]["excerpt"]
    assert len(payload["sources"][0]["excerpt"]) <= 400


def test_no_match_is_reported_to_the_model_and_the_client(client: TestClient, auth_headers: dict[str, str]) -> None:
    fake = _enable_fake_ai()
    uploaded = _upload(client, ["Historia do Brasil colonial."], auth_headers)

    payload = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"document_id": uploaded["document_id"], "message": "Como funciona a fotossintese?"},
    ).json()

    assert payload["has_relevant_match"] is False
    assert fake.last_call["has_relevant_match"] is False
    assert fake.last_call["has_material"] is True
    assert payload["sources"] == []
    assert "Historia do Brasil colonial" in fake.last_call["context"]


def test_chat_without_pdf_creates_conversation_and_answers(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    fake = _enable_fake_ai("Mitose e divisao celular.")

    response = client.post(CHAT_URL, headers=auth_headers, json={"message": "O que e mitose?"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["document_id"] is None
    assert payload["document_ids"] == []
    assert payload["used_documents"] is False
    assert payload["has_relevant_match"] is False
    assert payload["sources"] == []
    assert payload["answer"] == "Mitose e divisao celular."
    assert fake.last_call["has_material"] is False
    assert fake.last_call["context"] == ""
    assert fake.last_call["history"] == []


def test_chat_without_pdf_persists_and_sends_history(client: TestClient, auth_headers: dict[str, str]) -> None:
    fake = _enable_fake_ai("Ok")
    first = client.post(CHAT_URL, headers=auth_headers, json={"message": "O que e mitose?"}).json()

    second = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"conversation_id": first["conversation_id"], "message": "E a meiose?"},
    )

    assert second.status_code == 200
    detail = client.get(f"/api/conversations/{first['conversation_id']}", headers=auth_headers).json()
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant", "user", "assistant"]
    assert detail["document_ids"] == []
    assert fake.last_call["history"][0] == {"role": "user", "content": "O que e mitose?"}
    assert fake.last_call["history"][1]["role"] == "assistant"


def test_retrieval_ignores_documents_not_attached_to_the_conversation(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    fake = _enable_fake_ai()
    other = _upload(client, ["A fotossintese ocorre nos cloroplastos."], auth_headers)
    attached = _upload(client, ["A mitose divide celulas."], auth_headers)
    conversation = client.post(
        "/api/conversations",
        headers=auth_headers,
        json={"document_id": attached["document_id"]},
    ).json()

    payload = client.post(
        CHAT_URL,
        headers=auth_headers,
        json={"conversation_id": conversation["id"], "message": "Onde ocorre a fotossintese?"},
    ).json()

    assert other["document_id"] not in payload["document_ids"]
    assert payload["has_relevant_match"] is False
    assert "fotossintese" not in fake.last_call["context"].lower()
    assert "mitose" in fake.last_call["context"].lower()


def test_cannot_attach_another_users_document(client: TestClient) -> None:
    from tests.helpers import register_and_login

    _enable_fake_ai()
    alice = register_and_login(client, "alice-chat@example.com")
    bob = register_and_login(client, "bob-chat@example.com")
    alice_doc = _upload(client, ["Segredo da Alice sobre mitose"], alice)
    bob_conversation = client.post("/api/conversations", headers=bob, json={}).json()

    attached = client.post(
        f"/api/conversations/{bob_conversation['id']}/documents",
        headers=bob,
        json={"document_id": alice_doc["document_id"]},
    )
    chat = client.post(
        CHAT_URL,
        headers=bob,
        json={"conversation_id": bob_conversation["id"], "document_id": alice_doc["document_id"], "message": "Explique"},
    )

    assert attached.status_code == 404
    assert chat.status_code == 404
    assert client.get("/api/conversations", headers=bob).json()["items"][0]["document_ids"] == []

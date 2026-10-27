import json

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.questions import MAX_QUANTITY
from app.services.ai_client import AITimeoutError, get_ai_client
from tests.fakes import FakeAIClient
from tests.helpers import build_pdf, override_settings, register_and_login

GENERATE_PATH = "/api/conversations/{conversation_id}/questions/generate"
LIST_PATH = "/api/conversations/{conversation_id}/questions"
SUBSTANTIAL = (
    "Explique com detalhes o que e mitose, para que serve no organismo e como se diferencia da meiose."
)


def _questions_json(
    *,
    quantity: int = 5,
    difficulty: str = "medium",
    correct_option: str = "A",
    extra: dict | None = None,
) -> str:
    questions = []
    for index in range(quantity):
        item = {
            "stem": f"Qual afirmativa descreve o conceito {index + 1} da conversa?",
            "choices": [
                {"id": "A", "text": "Divisao celular que gera celulas geneticamente iguais."},
                {"id": "B", "text": "Processo exclusivo de producao de energia na mitocondria."},
                {"id": "C", "text": "Troca de gases nos alveolos pulmonares."},
                {"id": "D", "text": "Absorcao de agua apenas pela raiz."},
            ],
            "correct_option": correct_option,
            "explanation": "A mitose preserva o patrimonio genetico nas celulas-filhas.",
            "difficulty": difficulty,
        }
        questions.append(item)
    payload = {"questions": questions}
    if extra:
        payload.update(extra)
    return json.dumps(payload, ensure_ascii=False)


def _enable_questions_ai(
    content: str | None = None,
    completions: list[str | BaseException] | None = None,
) -> FakeAIClient:
    fake = FakeAIClient(content=content or _questions_json(), completions=completions)
    app.dependency_overrides[get_ai_client] = lambda: fake
    return fake


def _create_conversation(client: TestClient, auth_headers: dict[str, str]) -> str:
    created = client.post("/api/conversations", headers=auth_headers, json={})
    assert created.status_code == 201, created.text
    return created.json()["id"]


def _seed_history(client: TestClient, auth_headers: dict[str, str], conversation_id: str, message: str = SUBSTANTIAL) -> None:
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient("Explicacao persistida no historico")
    asked = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"conversation_id": conversation_id, "message": message},
    )
    assert asked.status_code == 200, asked.text


def _upload_and_attach(
    client: TestClient,
    auth_headers: dict[str, str],
    conversation_id: str,
    pages: list[str],
) -> str:
    uploaded = client.post(
        "/api/documents",
        headers=auth_headers,
        files={"file": ("aula.pdf", build_pdf(pages), "application/pdf")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["document_id"]
    attached = client.post(
        f"/api/conversations/{conversation_id}/documents",
        headers=auth_headers,
        json={"document_id": document_id},
    )
    assert attached.status_code == 200, attached.text
    return document_id


def test_generate_questions_with_custom_observation(client: TestClient, auth_headers: dict[str, str]) -> None:
    conversation_id = _create_conversation(client, auth_headers)
    _seed_history(client, auth_headers, conversation_id)
    fake = _enable_questions_ai(_questions_json(quantity=10, difficulty="hard"))
    observation = "Crie 10 questoes dificeis, no estilo ENEM, priorizando os conceitos mais importantes."

    response = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={"observation": observation, "quantity": 10, "difficulty": "hard"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["conversation_id"] == conversation_id
    assert body["observation"] == observation
    assert body["quantity"] == 10
    assert body["difficulty"] == "hard"
    assert body["question_type"] == "multiple_choice"
    assert len(body["questions"]) == 10
    assert body["questions"][0]["choices"][0]["id"] == "A"
    assert body["questions"][0]["correct_option"] == "A"
    assert body["used_documents"] is False
    assert body["sources"] == []
    prompt = fake.last_completion["messages"][-1]["content"]
    assert observation in prompt
    assert fake.last_completion["json_mode"] is True


def test_generate_questions_without_observation(client: TestClient, auth_headers: dict[str, str]) -> None:
    conversation_id = _create_conversation(client, auth_headers)
    _seed_history(client, auth_headers, conversation_id)
    fake = _enable_questions_ai()

    response = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["observation"] is None
    assert body["quantity"] == 5
    assert body["difficulty"] == "medium"
    assert len(body["questions"]) == 5
    assert "Sem observação extra" in fake.last_completion["messages"][-1]["content"]


def test_generate_questions_from_history_without_pdf(client: TestClient, auth_headers: dict[str, str]) -> None:
    conversation_id = _create_conversation(client, auth_headers)
    _seed_history(client, auth_headers, conversation_id)
    fake = _enable_questions_ai()

    response = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={"quantity": 2},
    )

    assert response.status_code == 201, response.text
    assert response.json()["used_documents"] is False
    assert response.json()["has_relevant_match"] is False
    assert fake.last_completion["messages"][1]["content"] == SUBSTANTIAL
    listed = client.get(LIST_PATH.format(conversation_id=conversation_id), headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == response.json()["id"]


def test_generate_questions_with_pdf_uses_real_sources(client: TestClient, auth_headers: dict[str, str]) -> None:
    conversation_id = _create_conversation(client, auth_headers)
    _seed_history(client, auth_headers, conversation_id)
    document_id = _upload_and_attach(
        client,
        auth_headers,
        conversation_id,
        ["Introducao ao caderno.", "A mitose e um processo de divisao celular.", "Referencias."],
    )
    fake = _enable_questions_ai(
        json.dumps(
            {
                "questions": json.loads(_questions_json(quantity=2))["questions"],
                "sources": [{"page": 99, "excerpt": "pagina inventada pelo modelo"}],
            }
        )
    )

    response = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={"observation": "Foque em mitose", "quantity": 2},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["used_documents"] is True
    assert body["has_relevant_match"] is True
    assert body["sources"][0]["page"] == 2
    assert body["sources"][0]["document_id"] == document_id
    assert "mitose" in body["sources"][0]["excerpt"].lower()
    assert all(source["page"] != 99 for source in body["sources"])
    assert "[Página 2]" in fake.last_completion["messages"][-1]["content"]


def test_generate_questions_rejects_insufficient_content(client: TestClient, auth_headers: dict[str, str]) -> None:
    conversation_id = _create_conversation(client, auth_headers)
    fake = _enable_questions_ai()

    response = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={},
    )

    assert response.status_code == 422, response.text
    assert "conteúdo suficiente" in response.json()["detail"]
    assert fake.completion_calls == 0
    empty = client.get(LIST_PATH.format(conversation_id=conversation_id), headers=auth_headers)
    assert empty.json()["total"] == 0


def test_generate_questions_rejects_missing_or_foreign_conversation(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    _enable_questions_ai()
    missing = client.post(
        GENERATE_PATH.format(conversation_id="00000000-0000-0000-0000-000000000000"),
        headers=auth_headers,
        json={},
    )
    assert missing.status_code == 404

    bob = register_and_login(client, "bob-questoes@example.com")
    bob_conversation = _create_conversation(client, bob)
    _seed_history(client, bob, bob_conversation)
    _enable_questions_ai()
    foreign = client.post(
        GENERATE_PATH.format(conversation_id=bob_conversation),
        headers=auth_headers,
        json={},
    )
    assert foreign.status_code == 404
    listed = client.get(LIST_PATH.format(conversation_id=bob_conversation), headers=auth_headers)
    assert listed.status_code == 404


def test_generate_questions_rejects_invalid_quantity_and_difficulty(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    conversation_id = _create_conversation(client, auth_headers)
    _enable_questions_ai()

    too_many = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={"quantity": MAX_QUANTITY + 1},
    )
    zero = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={"quantity": 0},
    )
    bad_difficulty = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={"difficulty": "impossible"},
    )
    too_long = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={"observation": "x" * 501},
    )

    assert too_many.status_code == 422
    assert zero.status_code == 422
    assert bad_difficulty.status_code == 422
    assert too_long.status_code == 422
    assert any(error["field"] == "quantity" for error in too_many.json()["errors"])
    assert any(error["field"] == "difficulty" for error in bad_difficulty.json()["errors"])


def test_generate_questions_retries_invalid_json_once(client: TestClient, auth_headers: dict[str, str]) -> None:
    conversation_id = _create_conversation(client, auth_headers)
    _seed_history(client, auth_headers, conversation_id)
    fake = _enable_questions_ai(completions=["nao-e-json", _questions_json(quantity=1)])

    response = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={"quantity": 1},
    )

    assert response.status_code == 201, response.text
    assert fake.completion_calls == 2
    assert len(response.json()["questions"]) == 1


def test_generate_questions_rejects_invalid_json_after_retry(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    conversation_id = _create_conversation(client, auth_headers)
    _seed_history(client, auth_headers, conversation_id)
    fake = _enable_questions_ai(content="```texto```")

    response = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={},
    )

    assert response.status_code == 502
    assert "válida" in response.json()["detail"]
    assert fake.completion_calls == 2
    assert "ai.test" not in response.text


def test_generate_questions_rejects_nonexistent_correct_option(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    conversation_id = _create_conversation(client, auth_headers)
    _seed_history(client, auth_headers, conversation_id)
    fake = _enable_questions_ai(content=_questions_json(quantity=1, correct_option="E"))

    response = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={"quantity": 1},
    )

    assert response.status_code == 502
    assert fake.completion_calls == 2
    assert client.get(LIST_PATH.format(conversation_id=conversation_id), headers=auth_headers).json()["total"] == 0


def test_generate_questions_handles_ollama_timeout(client: TestClient, auth_headers: dict[str, str]) -> None:
    conversation_id = _create_conversation(client, auth_headers)
    _seed_history(client, auth_headers, conversation_id)
    fake = _enable_questions_ai(completions=[AITimeoutError()])

    response = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={},
    )

    assert response.status_code == 503
    assert "demorou" in response.json()["detail"]
    assert fake.completion_calls == 1
    assert "Ollama" not in response.text
    assert "11434" not in response.text


def test_question_generation_preserves_chat_documents_and_conversations(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    conversation_id = _create_conversation(client, auth_headers)
    _seed_history(client, auth_headers, conversation_id)
    document_id = _upload_and_attach(
        client, auth_headers, conversation_id, ["A mitose divide celulas."]
    )
    before = client.get(f"/api/conversations/{conversation_id}", headers=auth_headers).json()
    _enable_questions_ai(_questions_json(quantity=2))

    generated = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={"quantity": 2},
    )
    assert generated.status_code == 201, generated.text

    after = client.get(f"/api/conversations/{conversation_id}", headers=auth_headers).json()
    assert after["messages"] == before["messages"]
    assert after["document_ids"] == [document_id]
    documents = client.get("/api/documents", headers=auth_headers)
    assert documents.status_code == 200
    assert documents.json()["total"] >= 1

    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient("Ainda funciona o chat")
    chat = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"conversation_id": conversation_id, "message": "Resuma o que ja vimos"},
    )
    assert chat.status_code == 200, chat.text
    assert chat.json()["answer"] == "Ainda funciona o chat"
    listed = client.get("/api/conversations", headers=auth_headers)
    assert listed.json()["total"] == 1


def test_question_generation_respects_context_limit_and_keep_alive_contract(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    override_settings(max_context_chars=200)
    conversation_id = _create_conversation(client, auth_headers)
    old = "A" * 200
    _seed_history(client, auth_headers, conversation_id, message=old)
    app.dependency_overrides[get_ai_client] = lambda: FakeAIClient("turno recente")
    recent = "Explique agora a diferenca pratica entre mitose e meiose no material estudado."
    asked = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"conversation_id": conversation_id, "message": recent},
    )
    assert asked.status_code == 200, asked.text

    fake = _enable_questions_ai(_questions_json(quantity=1))
    response = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={"quantity": 1},
    )
    assert response.status_code == 201, response.text
    history_contents = [item["content"] for item in fake.last_completion["messages"] if item["role"] != "system"]
    assert old not in history_contents
    assert any(recent in content for content in history_contents)
    assert fake.last_completion["json_mode"] is True
    assert response.json()["model"] == "gemma3:4b"


def test_blank_observation_is_treated_as_absent(client: TestClient, auth_headers: dict[str, str]) -> None:
    conversation_id = _create_conversation(client, auth_headers)
    _seed_history(client, auth_headers, conversation_id)
    _enable_questions_ai()

    response = client.post(
        GENERATE_PATH.format(conversation_id=conversation_id),
        headers=auth_headers,
        json={"observation": "   "},
    )

    assert response.status_code == 201, response.text
    assert response.json()["observation"] is None

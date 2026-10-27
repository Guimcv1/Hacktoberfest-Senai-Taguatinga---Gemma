import asyncio
import json

import httpx
import pytest

from app.services.ai_client import (
    AIClient,
    AIInvalidResponseError,
    AITimeoutError,
    AIUnavailableError,
)


VALID_RESPONSE = {
    "model": "gemma3:4b",
    "message": {"role": "assistant", "content": "Texto gerado pelo modelo"},
    "done": True,
}


def _run(client: AIClient):
    return asyncio.run(client.generate_explanation(question="O que e mitose?", context="[Página 2]\nMitose e divisao celular."))


def test_ai_client_sends_confirmed_payload() -> None:
    recorded: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        recorded["url"] = str(request.url)
        recorded["payload"] = json.loads(request.content)
        return httpx.Response(200, json=VALID_RESPONSE)

    client = AIClient(
        "http://ai.test",
        5.0,
        "gemma3:4b",
        transport=httpx.MockTransport(handler),
    )

    result = _run(client)

    assert recorded["url"] == "http://ai.test/api/chat"
    assert recorded["payload"]["model"] == "gemma3:4b"
    assert recorded["payload"]["stream"] is False
    assert recorded["payload"]["messages"][0]["role"] == "system"
    assert recorded["payload"]["messages"][1]["role"] == "user"
    assert "O que e mitose?" in recorded["payload"]["messages"][1]["content"]
    assert "[Página 2]" in recorded["payload"]["messages"][1]["content"]
    assert result.content == "Texto gerado pelo modelo"
    assert result.model == "gemma3:4b"
    assert "http://ai.test" not in result.content


def test_ai_client_accepts_valid_ollama_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=VALID_RESPONSE)

    client = AIClient("http://ai.test", 5.0, "gemma3:4b", transport=httpx.MockTransport(handler))
    result = _run(client)
    assert result.content == "Texto gerado pelo modelo"


def test_ai_client_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow")

    client = AIClient("http://ai.test", 5.0, "gemma3:4b", transport=httpx.MockTransport(handler))

    with pytest.raises(AITimeoutError) as exc_info:
        _run(client)

    assert "demorou" in exc_info.value.public_message
    assert "ai.test" not in exc_info.value.public_message


def test_ai_client_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "internal"})

    client = AIClient("http://ai.test", 5.0, "gemma3:4b", transport=httpx.MockTransport(handler))

    with pytest.raises(AIUnavailableError) as exc_info:
        _run(client)

    assert "indisponível" in exc_info.value.public_message
    assert "500" not in exc_info.value.public_message
    assert "ai.test" not in exc_info.value.public_message


def test_ai_client_invalid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="nao-json")

    client = AIClient("http://ai.test", 5.0, "gemma3:4b", transport=httpx.MockTransport(handler))

    with pytest.raises(AIInvalidResponseError):
        _run(client)


def test_ai_client_missing_message_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"model": "gemma3:4b", "done": True})

    client = AIClient("http://ai.test", 5.0, "gemma3:4b", transport=httpx.MockTransport(handler))

    with pytest.raises(AIInvalidResponseError):
        _run(client)


def test_ai_client_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    client = AIClient("http://ai.test", 5.0, "gemma3:4b", transport=httpx.MockTransport(handler))

    with pytest.raises(AIUnavailableError):
        _run(client)

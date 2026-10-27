import re
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.middleware import BodySizeLimitMiddleware, RateLimitMiddleware
from app.main import app
from app.services.ai_client import get_ai_client
from tests.helpers import build_pdf

ORIGIN = "http://localhost:5173"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def _inner_app() -> FastAPI:
    inner = FastAPI()

    @inner.get("/api/documents/{document_id}")
    def get_document(document_id: str) -> dict:
        return {"id": document_id}

    @inner.post("/api/auth/login")
    def login() -> dict:
        return {"ok": True}

    @inner.post("/api/documents")
    async def upload(request: Request) -> dict:
        return {"size": len(await request.body())}

    return inner


def _rate_limited(per_minute: int = 3, auth_per_minute: int = 2):
    clock = FakeClock()
    limits = SimpleNamespace(rate_limit_per_minute=per_minute, rate_limit_auth_per_minute=auth_per_minute)
    middleware = RateLimitMiddleware(_inner_app(), settings_provider=lambda: limits, clock=clock)
    return middleware, clock


def test_rate_limit_returns_429_with_retry_after() -> None:
    middleware, _clock = _rate_limited(per_minute=3)
    client = TestClient(middleware)

    statuses = [client.get("/api/documents/a").status_code for _ in range(3)]
    blocked = client.get("/api/documents/a")

    assert statuses == [200, 200, 200]
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "60"
    assert blocked.json()["detail"] == "Muitas requisições. Tente novamente em instantes."


def test_dynamic_paths_share_one_bucket_per_client() -> None:
    middleware, _clock = _rate_limited(per_minute=3)
    client = TestClient(middleware)

    for index in range(3):
        assert client.get(f"/api/documents/{index}").status_code == 200

    assert client.get("/api/documents/outro-id").status_code == 429
    assert middleware.tracked_keys == 1


def test_auth_routes_use_their_own_limit() -> None:
    middleware, _clock = _rate_limited(per_minute=10, auth_per_minute=2)
    client = TestClient(middleware)

    assert [client.post("/api/auth/login").status_code for _ in range(3)] == [200, 200, 429]
    assert client.get("/api/documents/a").status_code == 200


def test_window_slides_and_stale_clients_are_evicted() -> None:
    middleware, clock = _rate_limited(per_minute=1)
    first = TestClient(middleware, client=("10.0.0.1", 5000))
    second = TestClient(middleware, client=("10.0.0.2", 5000))

    assert first.get("/api/documents/a").status_code == 200
    assert second.get("/api/documents/a").status_code == 200
    assert first.get("/api/documents/a").status_code == 429
    assert middleware.tracked_keys == 2

    clock.now += 61
    assert first.get("/api/documents/a").status_code == 200
    assert middleware.tracked_keys == 1


def test_tracked_clients_are_capped() -> None:
    middleware, _clock = _rate_limited(per_minute=5)
    middleware.max_tracked_keys = 2

    for host in ("10.0.0.1", "10.0.0.2", "10.0.0.3"):
        assert TestClient(middleware, client=(host, 5000)).get("/api/documents/a").status_code == 200

    assert middleware.tracked_keys == 2


def test_zero_disables_rate_limit_and_options_are_never_limited() -> None:
    middleware, _clock = _rate_limited(per_minute=0, auth_per_minute=1)
    client = TestClient(middleware)

    assert all(client.get("/api/documents/a").status_code == 200 for _ in range(20))
    assert middleware.tracked_keys == 0
    assert client.options("/api/auth/login").status_code != 429
    assert client.options("/api/auth/login").status_code != 429


def test_upload_limit_rejects_declared_size_before_reading_body() -> None:
    limits = SimpleNamespace(max_pdf_size_bytes=1024)
    client = TestClient(BodySizeLimitMiddleware(_inner_app(), settings_provider=lambda: limits))
    allowed = 1024 + 1024 * 1024

    accepted = client.post("/api/documents", content=b"x" * allowed)
    rejected = client.post("/api/documents", content=b"x" * (allowed + 1))

    assert accepted.status_code == 200
    assert rejected.status_code == 413
    assert rejected.json()["detail"] == "Arquivo excede o tamanho máximo permitido."


def test_json_body_above_limit_is_rejected_before_authentication(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        content=b'{"email": "' + b"a" * (1024 * 1024) + b'"}',
        headers={"Content-Type": "application/json", "Origin": ORIGIN},
    )

    assert response.status_code == 413
    assert response.json()["detail"] == "A requisição excede o tamanho máximo permitido."
    assert response.headers.get("access-control-allow-origin") == ORIGIN
    assert response.headers.get("x-request-id")


def test_streamed_body_without_content_length_is_cut(client: TestClient) -> None:
    def chunks():
        for _ in range(5):
            yield b" " * (256 * 1024)

    response = client.post("/api/chat", content=chunks(), headers={"Content-Type": "application/json"})

    assert response.status_code == 413


def test_valid_client_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Request-ID": "front-123.abc"})

    assert response.headers["x-request-id"] == "front-123.abc"


@pytest.mark.parametrize("unsafe", ["tem espaco", "x" * 200, "a;b=c"])
def test_unsafe_client_request_id_is_replaced(client: TestClient, unsafe: str) -> None:
    response = client.get("/health", headers={"X-Request-ID": unsafe})

    assert response.headers["x-request-id"] != unsafe
    assert re.fullmatch(r"[0-9a-f]{32}", response.headers["x-request-id"])


def test_unexpected_error_returns_json_500_with_cors_and_request_id(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    class BrokenAI:
        async def generate_explanation(self, **kwargs):
            raise RuntimeError("detalhe interno sigiloso")

    app.dependency_overrides[get_ai_client] = lambda: BrokenAI()
    uploaded = client.post(
        "/api/documents",
        files={"file": ("aula.pdf", build_pdf(["Mitose"]), "application/pdf")},
        headers=auth_headers,
    ).json()

    response = client.post(
        "/api/chat",
        json={"document_id": uploaded["document_id"], "message": "Explique a mitose"},
        headers={**auth_headers, "Origin": ORIGIN},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Erro interno. Tente novamente mais tarde."}
    assert response.headers.get("access-control-allow-origin") == ORIGIN
    assert response.headers.get("x-request-id")
    assert "sigiloso" not in response.text


def test_rate_limited_response_keeps_cors_and_request_id(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_AUTH_PER_MINUTE", "2")
    get_settings.cache_clear()
    try:
        payload = {"email": "limite@example.com", "password": "senha1234"}
        headers = {"Origin": ORIGIN}
        responses = [client.post("/api/auth/login", json=payload, headers=headers) for _ in range(3)]
    finally:
        get_settings.cache_clear()

    assert [response.status_code for response in responses] == [401, 401, 429]
    assert responses[-1].headers.get("access-control-allow-origin") == ORIGIN
    assert responses[-1].headers.get("x-request-id")
    assert responses[-1].headers.get("retry-after")


def test_validation_errors_list_fields_without_echoing_input(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "nao-e-email", "password": "curta", "name": "Aluno"},
    )

    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == "Dados de entrada inválidos."
    errors = {item["field"]: item for item in body["errors"]}
    assert errors["email"]["message"] == "Endereço de e-mail inválido."
    assert errors["password"]["type"] == "string_too_short"
    assert errors["password"]["message"] == "Deve ter pelo menos 8 caractere(s)."
    assert "curta" not in response.text
    assert "nao-e-email" not in response.text

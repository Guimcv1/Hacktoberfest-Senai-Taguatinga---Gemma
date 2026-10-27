import inspect
import uuid
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from tests.helpers import build_pdf

UPLOAD_URL = "/api/documents"


def _post_file(
    client: TestClient,
    content: bytes,
    filename: str = "material.pdf",
    content_type: str = "application/pdf",
):
    return client.post(
        UPLOAD_URL,
        files={"file": (filename, content, content_type)},
    )


def test_upload_valid_pdf_returns_extracted_pages(client: TestClient) -> None:
    content = build_pdf(["Texto da primeira pagina", "Texto da segunda pagina"])

    response = _post_file(client, content, filename="material.pdf")

    assert response.status_code == 201
    payload = response.json()
    uuid.UUID(payload["document_id"])
    assert payload["filename"] == "material.pdf"
    assert payload["page_count"] == 2
    assert payload["pages"][0]["page_number"] == 1
    assert "Texto da primeira pagina" in payload["pages"][0]["text"]
    assert payload["pages"][1]["page_number"] == 2
    assert "Texto da segunda pagina" in payload["pages"][1]["text"]


def test_upload_preserves_page_numbers(client: TestClient) -> None:
    content = build_pdf(["Pagina A", "Pagina B", "Pagina C"])

    payload = _post_file(client, content).json()

    assert [page["page_number"] for page in payload["pages"]] == [1, 2, 3]


def test_upload_rejects_non_pdf_even_with_pdf_name_and_mime(client: TestClient) -> None:
    response = _post_file(
        client,
        b"isto nao e um pdf",
        filename="material.pdf",
        content_type="application/pdf",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Arquivo PDF inválido."


def test_upload_rejects_corrupted_pdf(client: TestClient) -> None:
    valid = build_pdf(["Conteudo"])
    corrupted = valid[:24]

    response = _post_file(client, corrupted, filename="quebrado.pdf")

    assert response.status_code == 400
    assert response.json()["detail"] == "Arquivo PDF inválido."


def test_upload_rejects_pdf_without_extractable_text(client: TestClient) -> None:
    content = build_pdf(["", ""])

    response = _post_file(client, content)

    assert response.status_code == 422
    assert response.json()["detail"] == "O PDF não contém texto extraível."


def test_upload_rejects_file_above_size_limit(client: TestClient) -> None:
    content = build_pdf(["Conteudo dentro do limite original"])
    app.dependency_overrides[get_settings] = lambda: SimpleNamespace(max_pdf_size_bytes=64)
    try:
        response = _post_file(client, content)
    finally:
        app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 413
    assert response.json()["detail"] == "Arquivo excede o tamanho máximo permitido."


def test_upload_does_not_depend_on_ai(client: TestClient) -> None:
    import app.api.routes.documents as documents_route

    source = inspect.getsource(documents_route)
    assert "ai_client" not in source
    assert "generate_explanation" not in source
    assert "get_ai_client" not in source

    content = build_pdf(["Texto independente da IA"])
    with (
        patch("app.services.ai_client.AIClient.generate_explanation") as mock_infer,
        patch("app.services.ai_client.get_ai_client") as mock_factory,
    ):
        response = _post_file(client, content)

    assert response.status_code == 201
    mock_infer.assert_not_called()
    mock_factory.assert_not_called()


def test_upload_accepts_valid_pdf_with_unrelated_mime_type(client: TestClient) -> None:
    content = build_pdf(["Conteudo real de PDF"])

    response = _post_file(
        client,
        content,
        filename="notas.bin",
        content_type="text/plain",
    )

    assert response.status_code == 201
    assert response.json()["filename"] == "notas.bin"

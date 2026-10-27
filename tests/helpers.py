import fitz
from fastapi.testclient import TestClient


def override_settings(**updates):
    """Substitui as configurações injetadas nas rotas; o conftest desfaz ao fim do teste."""
    from app.core.config import get_settings
    from app.main import app

    current = get_settings().model_copy(update=updates)
    app.dependency_overrides[get_settings] = lambda: current
    return current


def build_pdf(pages: list[str]) -> bytes:
    """Cria um PDF em memória, uma página por item da lista."""
    document = fitz.open()
    try:
        for text in pages:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        return document.tobytes()
    finally:
        document.close()


def register_and_login(
    client: TestClient,
    email: str,
    password: str = "senha1234",
    name: str = "Estudante",
) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "name": name},
    )
    if response.status_code == 409:
        response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code in {200, 201}, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}

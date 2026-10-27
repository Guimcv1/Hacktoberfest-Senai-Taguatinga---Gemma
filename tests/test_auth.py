from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app.core.config import get_settings


def test_register_and_me(client: TestClient) -> None:
    response = client.post(
        "/api/auth/register",
        json={"email": "nova@example.com", "password": "senha1234", "name": "Nova"},
    )
    assert response.status_code == 201
    token = response.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "nova@example.com"
    assert me.json()["name"] == "Nova"


def test_login_and_logout(client: TestClient) -> None:
    client.post("/api/auth/register", json={"email": "login@example.com", "password": "senha1234", "name": "L"})
    login = client.post("/api/auth/login", json={"email": "login@example.com", "password": "senha1234"})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/auth/me", headers=headers).status_code == 200
    logout = client.post("/api/auth/logout", headers=headers)
    assert logout.status_code == 204
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_login_rejects_wrong_password(client: TestClient) -> None:
    client.post("/api/auth/register", json={"email": "x@example.com", "password": "senha1234", "name": "X"})
    response = client.post("/api/auth/login", json={"email": "x@example.com", "password": "errada123"})
    assert response.status_code == 401
    assert "inválidos" in response.json()["detail"]


def test_duplicate_email_conflict(client: TestClient) -> None:
    payload = {"email": "dup@example.com", "password": "senha1234", "name": "Dup"}
    assert client.post("/api/auth/register", json=payload).status_code == 201
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_expired_token_is_rejected(client: TestClient) -> None:
    settings = get_settings()
    token = jwt.encode(
        {
            "sub": "missing-user",
            "jti": "expired-jti",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "type": "access",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.services.auth as auth_service
from app.core.config import get_settings
from app.db.models import RevokedToken, User
from app.services.auth import AuthError, register_user, revoke_token


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


def _register(client: TestClient, email: str, password: str = "senha1234", name: str = "Aluno"):
    return client.post("/api/auth/register", json={"email": email, "password": password, "name": name})


@pytest.mark.parametrize("password", ["a" * 73, "é" * 37])
def test_register_rejects_passwords_bcrypt_cannot_hash(client: TestClient, password: str) -> None:
    response = _register(client, "longa@example.com", password=password)

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "password"
    assert "72" in response.json()["errors"][0]["message"]


def test_password_with_exactly_72_bytes_works(client: TestClient) -> None:
    password = "ç" * 36

    assert _register(client, "limite@example.com", password=password).status_code == 201
    login = client.post("/api/auth/login", json={"email": "limite@example.com", "password": password})
    assert login.status_code == 200


def test_login_with_overlong_password_is_a_normal_failure(client: TestClient) -> None:
    _register(client, "normal@example.com")

    response = client.post("/api/auth/login", json={"email": "normal@example.com", "password": "a" * 100})

    assert response.status_code == 401


def test_register_strips_name_and_rejects_blank_name(client: TestClient) -> None:
    assert _register(client, "branco@example.com", name="   ").status_code == 422

    created = _register(client, "ana@example.com", name="  Ana  ")
    assert created.json()["user"]["name"] == "Ana"


def test_email_is_normalized(client: TestClient) -> None:
    _register(client, "Maiuscula@Example.com")

    assert _register(client, "maiuscula@example.com").status_code == 409
    login = client.post("/api/auth/login", json={"email": "MAIUSCULA@example.com", "password": "senha1234"})
    assert login.status_code == 200


def test_concurrent_registration_with_same_email_is_a_conflict(
    db: Session, db_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_hash = auth_service.hash_password

    def hash_while_another_request_wins(plain: str) -> str:
        other = db_session_factory()
        try:
            other.add(
                User(
                    id="vencedor",
                    email="corrida@example.com",
                    password_hash="hash",
                    name="Outro",
                    created_at=datetime.now(timezone.utc),
                )
            )
            other.commit()
        finally:
            other.close()
        return real_hash(plain)

    monkeypatch.setattr(auth_service, "hash_password", hash_while_another_request_wins)

    with pytest.raises(AuthError) as exc_info:
        register_user(db, email="corrida@example.com", password="senha1234", name="Eu")

    assert exc_info.value.code == "email_taken"
    assert db.scalar(select(func.count()).select_from(User)) == 1


@pytest.mark.parametrize(
    "authorization",
    ["Basic dXNlcjpwYXNz", "Bearer nao-e-um-jwt", "Bearer"],
)
def test_malformed_credentials_are_rejected_with_challenge(client: TestClient, authorization: str) -> None:
    response = client.get("/api/auth/me", headers={"Authorization": authorization})

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_token_signed_with_another_secret_is_rejected(client: TestClient) -> None:
    created = _register(client, "assinatura@example.com").json()
    forged = jwt.encode(
        {
            "sub": created["user"]["id"],
            "jti": "forjado",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "type": "access",
        },
        "outro-segredo-qualquer-com-mais-de-32-caracteres",
        algorithm="HS256",
    )

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {forged}"})

    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


def test_unsigned_token_is_rejected(client: TestClient) -> None:
    created = _register(client, "semassinatura@example.com").json()
    unsigned = jwt.encode({"sub": created["user"]["id"], "jti": "x", "type": "access"}, None, algorithm="none")

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {unsigned}"})

    assert response.status_code == 401


def test_logout_purges_revocations_that_already_expired(db: Session) -> None:
    now = datetime.now(timezone.utc)
    db.add(RevokedToken(jti="antigo", expires_at=now - timedelta(hours=1)))
    db.commit()

    revoke_token(db, "atual", now + timedelta(hours=1))

    assert db.get(RevokedToken, "antigo") is None
    assert db.get(RevokedToken, "atual") is not None

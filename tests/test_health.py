from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

import app.db.session as db_session
from app.db.migrations import head_revision
from app.db.session import get_db
from app.main import app
from app.services.ai_client import get_ai_client
from tests.helpers import override_settings


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "StudyBuddy AI"


def test_docs_are_available(client: TestClient) -> None:
    response = client.get("/docs")
    assert response.status_code == 200


def test_ready_reports_database(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {
        "status": "ok",
        "database": "ok",
        "migrations": "ok",
        "ai_configured": False,
        "ai": "not_checked",
    }


class _BrokenSession:
    def execute(self, *args, **kwargs):
        raise OperationalError("SELECT 1", {}, Exception("banco fora do ar"))

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


def test_ready_returns_503_when_database_is_down(client: TestClient) -> None:
    app.dependency_overrides[get_db] = lambda: _BrokenSession()

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "degraded"
    assert response.json()["database"] == "error"
    assert "banco fora do ar" not in response.text


def test_ready_returns_503_when_migrations_are_pending(client: TestClient) -> None:
    engine = db_session.engine
    with engine.begin() as connection:
        connection.execute(text("UPDATE alembic_version SET version_num = '000'"))
    try:
        response = client.get("/ready")
    finally:
        with engine.begin() as connection:
            connection.execute(text("UPDATE alembic_version SET version_num = :head"), {"head": head_revision()})

    assert response.status_code == 503
    assert response.json()["migrations"] == "pending"


class _PingAI:
    def __init__(self, reachable: bool) -> None:
        self.reachable = reachable
        self.pings = 0

    async def ping(self, **kwargs) -> bool:
        self.pings += 1
        return self.reachable


def test_ready_checks_ai_only_when_asked(client: TestClient) -> None:
    override_settings(ai_base_url="http://ia-interna.test")
    fake = _PingAI(reachable=True)
    app.dependency_overrides[get_ai_client] = lambda: fake

    unchecked = client.get("/ready")
    assert unchecked.json()["ai"] == "not_checked"
    assert fake.pings == 0

    checked = client.get("/ready", params={"check_ai": "true"})
    assert checked.status_code == 200
    assert checked.json()["ai"] == "ok"
    assert checked.json()["ai_configured"] is True
    assert fake.pings == 1
    assert "ia-interna.test" not in checked.text


def test_unreachable_ai_does_not_make_the_api_unready(client: TestClient) -> None:
    override_settings(ai_base_url="http://ia-interna.test")
    app.dependency_overrides[get_ai_client] = lambda: _PingAI(reachable=False)

    response = client.get("/ready", params={"check_ai": "true"})

    assert response.status_code == 200
    assert response.json()["ai"] == "unreachable"


def test_ai_check_without_configuration(client: TestClient) -> None:
    fake = _PingAI(reachable=True)
    app.dependency_overrides[get_ai_client] = lambda: fake

    response = client.get("/ready", params={"check_ai": "true"})

    assert response.json()["ai"] == "not_configured"
    assert fake.pings == 0

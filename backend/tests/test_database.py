from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Conversation, User
from app.db.types import UTCDateTime
from tests.helpers import build_pdf

BRASILIA = timezone(timedelta(hours=-3))


def _is_explicit_utc(value: str) -> bool:
    return value.endswith("Z") or value.endswith("+00:00")


def _user(user_id: str, email: str, password_hash: str = "hash") -> User:
    return User(
        id=user_id,
        email=email,
        password_hash=password_hash,
        name="Fuso",
        created_at=datetime.now(timezone.utc),
    )


def test_api_timestamps_are_explicit_utc(client: TestClient) -> None:
    registered = client.post(
        "/api/auth/register",
        json={"email": "fuso@example.com", "password": "senha1234", "name": "Fuso"},
    )
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    uploaded = client.post(
        "/api/documents",
        files={"file": ("aula.pdf", build_pdf(["Conteudo"]), "application/pdf")},
        headers=headers,
    )
    detail = client.get(f"/api/documents/{uploaded.json()['document_id']}", headers=headers).json()

    assert _is_explicit_utc(registered.json()["user"]["created_at"])
    assert _is_explicit_utc(detail["created_at"])
    assert _is_explicit_utc(detail["expires_at"])


def test_round_trip_preserves_the_instant_in_utc(db: Session) -> None:
    local = datetime(2026, 10, 27, 9, 30, tzinfo=BRASILIA)
    user = _user("u-fuso", "instante@example.com")
    user.created_at = local
    db.add(user)
    db.commit()
    db.expire_all()

    loaded = db.get(User, "u-fuso")

    assert loaded.created_at == local
    assert loaded.created_at.utcoffset() == timedelta(0)
    assert loaded.created_at.hour == 12


def test_naive_values_are_treated_as_utc() -> None:
    column_type = UTCDateTime()
    naive = datetime(2026, 1, 1, 12, 0)

    assert column_type.process_result_value(naive, None) == naive.replace(tzinfo=timezone.utc)
    assert column_type.process_bind_param(naive, None).tzinfo == timezone.utc
    assert column_type.process_bind_param(datetime(2026, 1, 1, 9, 0, tzinfo=BRASILIA), None).hour == 12


def test_foreign_keys_are_enforced(db: Session) -> None:
    now = datetime.now(timezone.utc)
    db.add(
        Conversation(
            id="c-orfa",
            user_id="inexistente",
            document_id="inexistente",
            title="Orfa",
            created_at=now,
            updated_at=now,
        )
    )

    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_database_errors_do_not_expose_bound_parameters(db: Session) -> None:
    db.add(_user("u-1", "duplicado@example.com"))
    db.commit()
    db.add(_user("u-2", "duplicado@example.com", password_hash="hash-que-nao-pode-vazar"))

    with pytest.raises(IntegrityError) as exc_info:
        db.commit()
    db.rollback()

    assert "hash-que-nao-pode-vazar" not in str(exc_info.value)
    assert "hidden" in str(exc_info.value)

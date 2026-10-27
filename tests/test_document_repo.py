from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import app.services.document_repo as document_repo
from app.core.config import Settings, get_settings
from app.db.models import Conversation, Document, User
from app.schemas.documents import ExtractedDocument, ExtractedPage
from app.services.document_repo import (
    DocumentNotFoundError,
    DocumentStoreFullError,
    DocumentTooLargeError,
    content_hash,
    expire_document,
    get_owned_document,
    purge_expired,
    save_document,
)


def _extracted(*texts: str) -> ExtractedDocument:
    pages = [ExtractedPage(page_number=index, text=text) for index, text in enumerate(texts, start=1)]
    return ExtractedDocument(page_count=len(pages), pages=pages)


def _add_user(db: Session, user_id: str) -> None:
    db.add(
        User(
            id=user_id,
            email=f"{user_id}@example.com",
            password_hash="hash",
            name=user_id,
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def _save(db: Session, user_id: str, *texts: str, **limits) -> tuple[Document, bool]:
    return save_document(
        db,
        user_id=user_id,
        filename="material.pdf",
        extracted=_extracted(*texts),
        file_hash=content_hash("|".join(texts).encode()),
        settings=get_settings().model_copy(update=limits),
    )


def _count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model))


def test_save_and_get_owned_document(db: Session) -> None:
    _add_user(db, "ana")
    stored, deduplicated = _save(db, "ana", "Pagina um", "Pagina dois")

    loaded = get_owned_document(db, "ana", stored.id)

    assert deduplicated is False
    assert loaded.page_count == 2
    assert loaded.text_chars == len("Pagina um") + len("Pagina dois")


def test_other_user_cannot_get_document(db: Session) -> None:
    _add_user(db, "ana")
    _add_user(db, "bia")
    stored, _ = _save(db, "ana", "Segredo")

    with pytest.raises(DocumentNotFoundError):
        get_owned_document(db, "bia", stored.id)


def test_expired_document_is_purged_with_its_conversations(db: Session) -> None:
    _add_user(db, "ana")
    stored, _ = _save(db, "ana", "Texto")
    now = datetime.now(timezone.utc)
    db.add(Conversation(id="conversa", user_id="ana", document_id=stored.id, title="t", created_at=now, updated_at=now))
    db.commit()

    expire_document(db, stored.id)

    with pytest.raises(DocumentNotFoundError):
        get_owned_document(db, "ana", stored.id)
    assert _count(db, Document) == 0
    assert _count(db, Conversation) == 0


def test_global_purge_covers_every_user(db: Session) -> None:
    for user_id in ("ana", "bia"):
        _add_user(db, user_id)
        stored, _ = _save(db, user_id, f"Texto de {user_id}")
        expire_document(db, stored.id)

    assert purge_expired(db) == 2
    assert _count(db, Document) == 0


def test_expiry_frees_capacity(db: Session) -> None:
    _add_user(db, "ana")
    first, _ = _save(db, "ana", "Primeiro", max_stored_documents=1)
    expire_document(db, first.id)

    second, _ = _save(db, "ana", "Segundo", max_stored_documents=1)

    assert second.id != first.id


def test_document_count_limit_is_per_user(db: Session) -> None:
    _add_user(db, "ana")
    _add_user(db, "bia")
    _save(db, "ana", "Primeiro", max_stored_documents=1)

    with pytest.raises(DocumentStoreFullError) as exc_info:
        _save(db, "ana", "Segundo", max_stored_documents=1)

    assert "Exclua documentos antigos" in exc_info.value.message
    _save(db, "bia", "Outro usuario", max_stored_documents=1)


def test_text_quota_counts_existing_documents(db: Session) -> None:
    _add_user(db, "ana")
    _save(db, "ana", "a" * 600, max_stored_text_chars=1000)

    with pytest.raises(DocumentStoreFullError):
        _save(db, "ana", "b" * 600, max_stored_text_chars=1000)


def test_single_document_above_quota_has_its_own_error(db: Session) -> None:
    _add_user(db, "ana")

    with pytest.raises(DocumentTooLargeError):
        _save(db, "ana", "a" * 1001, max_stored_text_chars=1000)


def test_same_pdf_is_deduplicated(db: Session) -> None:
    _add_user(db, "ana")
    first, _ = _save(db, "ana", "Mesmo conteudo")

    again, deduplicated = _save(db, "ana", "Mesmo conteudo")

    assert deduplicated is True
    assert again.id == first.id
    assert _count(db, Document) == 1


def test_concurrent_upload_of_same_pdf_returns_existing(
    db: Session, db_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add_user(db, "ana")
    real_uuid4 = document_repo.uuid4

    def uuid_after_another_request_saved_the_same_pdf():
        monkeypatch.setattr(document_repo, "uuid4", real_uuid4)
        other = db_session_factory()
        try:
            _save(other, "ana", "Conteudo concorrente")
        finally:
            other.close()
        return real_uuid4()

    monkeypatch.setattr(document_repo, "uuid4", uuid_after_another_request_saved_the_same_pdf)

    stored, deduplicated = _save(db, "ana", "Conteudo concorrente")

    assert deduplicated is True
    assert _count(db, Document) == 1
    assert stored.text_chars == len("Conteudo concorrente")


def test_documents_live_for_seven_days_by_default() -> None:
    assert Settings.model_fields["document_ttl_minutes"].default == 7 * 24 * 60

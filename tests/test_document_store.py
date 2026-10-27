from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.documents import ExtractedDocument, ExtractedPage
from app.services.document_store import (
    DocumentNotFoundError,
    DocumentStore,
    DocumentStoreFullError,
)


def _extracted(*texts: str) -> ExtractedDocument:
    pages = [ExtractedPage(page_number=index, text=text) for index, text in enumerate(texts, start=1)]
    return ExtractedDocument(page_count=len(pages), pages=pages)


def test_save_and_get_document_by_id() -> None:
    store = DocumentStore(ttl_seconds=1800, max_documents=10, max_text_chars=10_000)
    stored = store.save(filename="material.pdf", extracted=_extracted("Pagina um", "Pagina dois"))

    retrieved = store.get(stored.document_id)

    assert retrieved.document_id == stored.document_id
    assert retrieved.filename == "material.pdf"
    assert retrieved.page_count == 2
    assert retrieved.pages[0].page_number == 1
    assert retrieved.created_at.tzinfo is not None


def test_missing_document_raises() -> None:
    store = DocumentStore(ttl_seconds=1800, max_documents=10, max_text_chars=10_000)

    with pytest.raises(DocumentNotFoundError):
        store.get("inexistente")


def test_expired_document_is_not_accessible() -> None:
    store = DocumentStore(ttl_seconds=1800, max_documents=10, max_text_chars=10_000)
    stored = store.save(filename="material.pdf", extracted=_extracted("Texto"))
    store.expire(stored.document_id)

    with pytest.raises(DocumentNotFoundError):
        store.get(stored.document_id)


def test_purge_expired_frees_capacity() -> None:
    store = DocumentStore(ttl_seconds=1800, max_documents=1, max_text_chars=10_000)
    first = store.save(filename="um.pdf", extracted=_extracted("Primeiro"))
    store.expire(first.document_id)

    second = store.save(filename="dois.pdf", extracted=_extracted("Segundo"))

    assert second.filename == "dois.pdf"
    with pytest.raises(DocumentNotFoundError):
        store.get(first.document_id)


def test_rejects_when_document_limit_exceeded() -> None:
    store = DocumentStore(ttl_seconds=1800, max_documents=1, max_text_chars=10_000)
    store.save(filename="um.pdf", extracted=_extracted("Primeiro"))

    with pytest.raises(DocumentStoreFullError):
        store.save(filename="dois.pdf", extracted=_extracted("Segundo"))


def test_clear_removes_all_documents() -> None:
    store = DocumentStore(ttl_seconds=1800, max_documents=10, max_text_chars=10_000)
    stored = store.save(filename="material.pdf", extracted=_extracted("Texto"))
    store.clear()

    with pytest.raises(DocumentNotFoundError):
        store.get(stored.document_id)


def test_clock_expiry_without_helper() -> None:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    store = DocumentStore(ttl_seconds=60, max_documents=10, max_text_chars=10_000)
    store._now = lambda: start
    stored = store.save(filename="material.pdf", extracted=_extracted("Texto"))
    store._now = lambda: start + timedelta(minutes=2)

    with pytest.raises(DocumentNotFoundError):
        store.get(stored.document_id)

"""Repositório temporário de documentos em memória. Os dados se perdem ao reiniciar."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.core.config import Settings, get_settings
from app.schemas.documents import ExtractedDocument, ExtractedPage


class DocumentStoreError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class DocumentNotFoundError(DocumentStoreError):
    def __init__(self, message: str = "Documento não encontrado ou expirado.") -> None:
        super().__init__("document_not_found", message)


class DocumentStoreFullError(DocumentStoreError):
    def __init__(self, message: str = "Limite temporário de documentos atingido. Tente novamente mais tarde.") -> None:
        super().__init__("document_store_full", message)


@dataclass
class StoredDocument:
    document_id: str
    filename: str
    pages: list[ExtractedPage]
    page_count: int
    created_at: datetime
    text_chars: int = field(init=False)

    def __post_init__(self) -> None:
        self.text_chars = sum(len(page.text) for page in self.pages)

    def as_extracted(self) -> ExtractedDocument:
        return ExtractedDocument(page_count=self.page_count, pages=self.pages)

    def is_expired(self, *, now: datetime, ttl_seconds: int) -> bool:
        return now >= self.created_at + timedelta(seconds=ttl_seconds)


class DocumentStore:
    def __init__(
        self,
        *,
        ttl_seconds: int,
        max_documents: int,
        max_text_chars: int,
    ) -> None:
        self.ttl_seconds = ttl_seconds
        self.max_documents = max_documents
        self.max_text_chars = max_text_chars
        self._items: dict[str, StoredDocument] = {}
        self._lock = threading.Lock()
        self._now = lambda: datetime.now(timezone.utc)

    @classmethod
    def from_settings(cls, settings: Settings) -> DocumentStore:
        return cls(
            ttl_seconds=settings.document_ttl_seconds,
            max_documents=settings.max_stored_documents,
            max_text_chars=settings.max_stored_text_chars,
        )

    def save(self, *, filename: str, extracted: ExtractedDocument) -> StoredDocument:
        incoming_chars = sum(len(page.text) for page in extracted.pages)
        if incoming_chars > self.max_text_chars:
            raise DocumentStoreFullError()

        with self._lock:
            self._purge_expired_locked()
            used_chars = sum(item.text_chars for item in self._items.values())
            if len(self._items) >= self.max_documents or used_chars + incoming_chars > self.max_text_chars:
                raise DocumentStoreFullError()

            stored = StoredDocument(
                document_id=str(uuid4()),
                filename=filename,
                pages=list(extracted.pages),
                page_count=extracted.page_count,
                created_at=self._now(),
            )
            self._items[stored.document_id] = stored
            return stored

    def get(self, document_id: str) -> StoredDocument:
        with self._lock:
            self._purge_expired_locked()
            stored = self._items.get(document_id)
            if stored is None:
                raise DocumentNotFoundError()
            return stored

    def expire(self, document_id: str) -> None:
        """Marca o documento como expirado. Usado pelos testes."""
        with self._lock:
            stored = self._items.get(document_id)
            if stored is None:
                raise DocumentNotFoundError()
            stored.created_at = self._now() - timedelta(seconds=self.ttl_seconds + 1)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def _purge_expired_locked(self) -> None:
        now = self._now()
        expired = [
            document_id
            for document_id, stored in self._items.items()
            if stored.is_expired(now=now, ttl_seconds=self.ttl_seconds)
        ]
        for document_id in expired:
            del self._items[document_id]


_store: DocumentStore | None = None
_store_lock = threading.Lock()


def get_document_store() -> DocumentStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = DocumentStore.from_settings(get_settings())
    return _store

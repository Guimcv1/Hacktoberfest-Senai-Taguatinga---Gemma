from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.deps import utcnow
from app.db.models import Document
from app.schemas.documents import ExtractedDocument, ExtractedPage


class DocumentAccessError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class DocumentNotFoundError(DocumentAccessError):
    def __init__(self) -> None:
        super().__init__("document_not_found", "Documento não encontrado ou expirado.")


class DocumentStoreFullError(DocumentAccessError):
    def __init__(self) -> None:
        super().__init__(
            "document_store_full",
            "Limite temporário de documentos atingido. Tente novamente mais tarde.",
        )


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def pages_from_json(raw: str) -> list[ExtractedPage]:
    payload = json.loads(raw)
    return [ExtractedPage.model_validate(item) for item in payload]


def extracted_from_row(row: Document) -> ExtractedDocument:
    pages = pages_from_json(row.pages_json)
    return ExtractedDocument(page_count=row.page_count, pages=pages)


def purge_expired(db: Session, user_id: str | None = None) -> None:
    now = utcnow()
    query = select(Document).where(Document.expires_at <= now)
    if user_id is not None:
        query = query.where(Document.user_id == user_id)
    for row in db.scalars(query).all():
        db.delete(row)
    db.commit()


def save_document(
    db: Session,
    *,
    user_id: str,
    filename: str,
    extracted: ExtractedDocument,
    file_hash: str,
    settings: Settings,
) -> tuple[Document, bool]:
    purge_expired(db, user_id)
    existing = db.scalar(
        select(Document).where(Document.user_id == user_id, Document.content_hash == file_hash)
    )
    if existing is not None and existing.expires_at > utcnow():
        return existing, True

    incoming_chars = sum(len(page.text) for page in extracted.pages)
    if incoming_chars > settings.max_stored_text_chars:
        raise DocumentStoreFullError()

    used_chars = db.scalar(
        select(func.coalesce(func.sum(Document.text_chars), 0)).where(Document.user_id == user_id)
    ) or 0
    count = db.scalar(select(func.count()).select_from(Document).where(Document.user_id == user_id)) or 0
    if count >= settings.max_stored_documents or used_chars + incoming_chars > settings.max_stored_text_chars:
        raise DocumentStoreFullError()

    now = utcnow()
    row = Document(
        id=str(uuid4()),
        user_id=user_id,
        filename=filename,
        content_hash=file_hash,
        page_count=extracted.page_count,
        text_chars=incoming_chars,
        pages_json=json.dumps([page.model_dump() for page in extracted.pages], ensure_ascii=False),
        created_at=now,
        expires_at=now + timedelta(seconds=settings.document_ttl_seconds),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, False


def get_owned_document(db: Session, user_id: str, document_id: str) -> Document:
    purge_expired(db, user_id)
    row = db.get(Document, document_id)
    if row is None or row.user_id != user_id or row.expires_at <= utcnow():
        raise DocumentNotFoundError()
    return row


def list_documents(db: Session, user_id: str, *, limit: int, offset: int) -> tuple[list[Document], int]:
    purge_expired(db, user_id)
    total = db.scalar(select(func.count()).select_from(Document).where(Document.user_id == user_id)) or 0
    rows = db.scalars(
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows), total


def delete_document(db: Session, user_id: str, document_id: str) -> None:
    row = get_owned_document(db, user_id, document_id)
    db.delete(row)
    db.commit()


def expire_document(db: Session, document_id: str) -> None:
    row = db.get(Document, document_id)
    if row is None:
        raise DocumentNotFoundError()
    row.expires_at = utcnow()
    db.commit()

"""Upload e ciclo de vida de PDFs do usuário autenticado."""

from __future__ import annotations

import logging
from typing import BinaryIO

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.documents import (
    DocumentDetail,
    DocumentListResponse,
    DocumentMeta,
    DocumentUploadResponse,
)
from app.services.document_repo import (
    DocumentAccessError,
    DocumentNotFoundError,
    DocumentStoreFullError,
    DocumentTooLargeError,
    content_hash,
    delete_document,
    extracted_from_row,
    get_owned_document,
    list_documents,
    pages_from_json,
    save_document,
)
from app.services.documents import (
    DocumentProcessingError,
    PdfTooLargeError,
    extract_pdf,
    sanitize_filename,
)

logger = logging.getLogger("studybuddy")

router = APIRouter(prefix="/api", tags=["documents"])

_READ_CHUNK_SIZE = 64 * 1024

_HTTP_STATUS_BY_CODE = {
    "invalid_pdf": status.HTTP_400_BAD_REQUEST,
    "empty_pdf": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "pdf_too_large": status.HTTP_413_CONTENT_TOO_LARGE,
    "pdf_too_many_pages": status.HTTP_422_UNPROCESSABLE_CONTENT,
}


def _meta(row) -> DocumentMeta:
    return DocumentMeta(
        document_id=row.id,
        filename=row.filename,
        page_count=row.page_count,
        text_chars=row.text_chars,
        created_at=row.created_at,
        expires_at=row.expires_at,
    )


@router.post(
    "/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar PDF",
)
def upload_document(
    file: UploadFile = File(..., description="Arquivo PDF enviado no campo file."),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentUploadResponse:
    # Rota síncrona: a extração com PyMuPDF roda no threadpool e não trava o event loop.
    filename = sanitize_filename(file.filename)
    try:
        content = _read_upload_limited(file.file, settings.max_pdf_size_bytes)
        extracted = extract_pdf(
            content,
            max_size_bytes=settings.max_pdf_size_bytes,
            max_pages=settings.max_pdf_pages,
        )
        stored, deduplicated = save_document(
            db,
            user_id=current_user.id,
            filename=filename,
            extracted=extracted,
            file_hash=content_hash(content),
            settings=settings,
        )
    except DocumentProcessingError as exc:
        raise HTTPException(
            status_code=_HTTP_STATUS_BY_CODE.get(exc.code, status.HTTP_400_BAD_REQUEST),
            detail=exc.message,
        ) from None
    except DocumentTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=exc.message) from None
    except DocumentStoreFullError as exc:
        raise HTTPException(status_code=status.HTTP_507_INSUFFICIENT_STORAGE, detail=exc.message) from None

    logger.info("PDF processado: document_id=%s page_count=%s", stored.id, stored.page_count)
    return DocumentUploadResponse(
        document_id=stored.id,
        filename=stored.filename,
        page_count=stored.page_count,
        pages=pages_from_json(stored.pages_json) if deduplicated else extracted.pages,
        deduplicated=deduplicated,
    )


@router.get("/documents", response_model=DocumentListResponse)
def list_user_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentListResponse:
    rows, total = list_documents(db, current_user.id, limit=limit, offset=offset)
    return DocumentListResponse(items=[_meta(row) for row in rows], total=total, limit=limit, offset=offset)


@router.get("/documents/{document_id}", response_model=DocumentDetail)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentDetail:
    try:
        row = get_owned_document(db, current_user.id, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from None
    extracted = extracted_from_row(row)
    return DocumentDetail(**_meta(row).model_dump(), pages=extracted.pages)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    try:
        delete_document(db, current_user.id, document_id)
    except DocumentAccessError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message) from None


def _read_upload_limited(stream: BinaryIO, max_size_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = stream.read(_READ_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size_bytes:
            raise PdfTooLargeError()
        chunks.append(chunk)
    return b"".join(chunks)

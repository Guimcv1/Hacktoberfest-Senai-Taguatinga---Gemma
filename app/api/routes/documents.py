"""Upload e processamento HTTP de PDFs."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.core.config import Settings, get_settings
from app.schemas.documents import DocumentUploadResponse
from app.services.document_store import DocumentStoreFullError, get_document_store
from app.services.documents import (
    DocumentProcessingError,
    PdfTooLargeError,
    extract_pdf,
)

logger = logging.getLogger("studybuddy")

router = APIRouter(prefix="/api", tags=["documents"])

_READ_CHUNK_SIZE = 64 * 1024

_HTTP_STATUS_BY_CODE = {
    "invalid_pdf": status.HTTP_400_BAD_REQUEST,
    "empty_pdf": status.HTTP_422_UNPROCESSABLE_CONTENT,
    "pdf_too_large": status.HTTP_413_CONTENT_TOO_LARGE,
}


@router.post(
    "/documents",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enviar PDF",
    responses={
        400: {"description": "Arquivo que não é um PDF válido ou está corrompido."},
        413: {"description": "Arquivo acima do limite configurado em MAX_PDF_SIZE_MB."},
        422: {"description": "PDF sem texto extraível ou formulário inválido."},
    },
)
async def upload_document(
    file: UploadFile = File(..., description="Arquivo PDF enviado no campo file."),
    settings: Settings = Depends(get_settings),
) -> DocumentUploadResponse:
    filename = Path(file.filename or "document.pdf").name

    try:
        content = await _read_upload_limited(file, settings.max_pdf_size_bytes)
        extracted = extract_pdf(content, max_size_bytes=settings.max_pdf_size_bytes)
    except DocumentProcessingError as exc:
        raise HTTPException(
            status_code=_HTTP_STATUS_BY_CODE.get(exc.code, status.HTTP_400_BAD_REQUEST),
            detail=exc.message,
        ) from None
    finally:
        await file.close()

    try:
        stored = get_document_store().save(filename=filename, extracted=extracted)
    except DocumentStoreFullError as exc:
        raise HTTPException(
            status_code=status.HTTP_507_INSUFFICIENT_STORAGE,
            detail=exc.message,
        ) from None

    logger.info(
        "PDF processado: document_id=%s filename=%s page_count=%s",
        stored.document_id,
        filename,
        stored.page_count,
    )
    return DocumentUploadResponse(
        document_id=stored.document_id,
        filename=stored.filename,
        page_count=stored.page_count,
        pages=stored.pages,
    )


async def _read_upload_limited(upload: UploadFile, max_size_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(_READ_CHUNK_SIZE)
        if not chunk:
            break
        total += len(chunk)
        if total > max_size_bytes:
            raise PdfTooLargeError()
        chunks.append(chunk)
    return b"".join(chunks)

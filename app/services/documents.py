"""Validação e extração de texto de PDFs, independente da camada HTTP."""

from __future__ import annotations

import unicodedata

import pymupdf

from app.schemas.documents import ExtractedDocument, ExtractedPage

DEFAULT_FILENAME = "document.pdf"
MAX_FILENAME_CHARS = 255


class DocumentProcessingError(Exception):
    """Erro de domínio no processamento de documentos."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class InvalidPdfError(DocumentProcessingError):
    def __init__(self, message: str = "Arquivo PDF inválido.") -> None:
        super().__init__("invalid_pdf", message)


class EmptyPdfError(DocumentProcessingError):
    def __init__(self, message: str = "O PDF não contém texto extraível.") -> None:
        super().__init__("empty_pdf", message)


class PdfTooLargeError(DocumentProcessingError):
    def __init__(self, message: str = "Arquivo excede o tamanho máximo permitido.") -> None:
        super().__init__("pdf_too_large", message)


class PdfTooManyPagesError(DocumentProcessingError):
    def __init__(self) -> None:
        super().__init__("pdf_too_many_pages", "O PDF excede o limite de páginas.")


def sanitize_filename(raw: str | None) -> str:
    """Mantém só o nome exibível: sem caminho, caracteres de controle ou de direção (bidi)."""
    name = (raw or "").replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(char for char in name if unicodedata.category(char) not in {"Cc", "Cf"}).strip()
    if not name or name in {".", ".."}:
        return DEFAULT_FILENAME
    if len(name) <= MAX_FILENAME_CHARS:
        return name
    stem, dot, extension = name.rpartition(".")
    if dot and stem and len(extension) <= 16:
        return f"{stem[: MAX_FILENAME_CHARS - len(extension) - 1]}.{extension}"
    return name[:MAX_FILENAME_CHARS]


def extract_pdf(
    content: bytes,
    *,
    max_size_bytes: int | None = None,
    max_pages: int | None = None,
) -> ExtractedDocument:
    """Valida um PDF e extrai o texto de cada página, preservando a numeração.

    OCR não está implementado: PDFs só com imagem são rejeitados como sem texto.
    """
    if not content:
        raise InvalidPdfError()

    if max_size_bytes is not None and len(content) > max_size_bytes:
        raise PdfTooLargeError()

    if not content.startswith(b"%PDF"):
        raise InvalidPdfError()

    try:
        document = pymupdf.open(stream=content, filetype="pdf")
    except Exception:
        raise InvalidPdfError() from None

    try:
        return _extract_pages(document, max_pages=max_pages)
    except DocumentProcessingError:
        raise
    except Exception:
        raise InvalidPdfError() from None
    finally:
        document.close()


def _extract_pages(document: pymupdf.Document, *, max_pages: int | None = None) -> ExtractedDocument:
    if document.is_encrypted or document.needs_pass:
        raise InvalidPdfError("PDF protegido por senha não é suportado.")

    if document.page_count < 1:
        raise InvalidPdfError()
    if max_pages is not None and document.page_count > max_pages:
        raise PdfTooManyPagesError()

    pages: list[ExtractedPage] = []
    has_extractable_text = False

    for page_number, page in enumerate(document, start=1):
        text = page.get_text("text") or ""
        if text.strip():
            has_extractable_text = True
        pages.append(ExtractedPage(page_number=page_number, text=text))

    if not has_extractable_text:
        raise EmptyPdfError()

    return ExtractedDocument(page_count=document.page_count, pages=pages)

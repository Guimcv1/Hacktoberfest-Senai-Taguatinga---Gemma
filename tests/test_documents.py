import pytest

from app.services.documents import (
    EmptyPdfError,
    InvalidPdfError,
    PdfTooLargeError,
    extract_pdf,
)
from tests.helpers import build_pdf


def test_extract_valid_pdf_preserves_page_numbers() -> None:
    content = build_pdf(["Conteudo da pagina 1", "Conteudo da pagina 2"])

    result = extract_pdf(content)

    assert result.page_count == 2
    assert [page.page_number for page in result.pages] == [1, 2]
    assert "Conteudo da pagina 1" in result.pages[0].text
    assert "Conteudo da pagina 2" in result.pages[1].text


def test_extract_invalid_pdf_raises() -> None:
    with pytest.raises(InvalidPdfError) as exc_info:
        extract_pdf(b"isto nao e um pdf")

    assert exc_info.value.code == "invalid_pdf"
    assert str(exc_info.value) == "Arquivo PDF inválido."


def test_extract_empty_bytes_raises_invalid_pdf() -> None:
    with pytest.raises(InvalidPdfError):
        extract_pdf(b"")


def test_extract_pdf_without_text_raises() -> None:
    content = build_pdf(["", ""])

    with pytest.raises(EmptyPdfError) as exc_info:
        extract_pdf(content)

    assert exc_info.value.code == "empty_pdf"
    assert str(exc_info.value) == "O PDF não contém texto extraível."


def test_extract_pdf_rejects_oversized_file() -> None:
    content = build_pdf(["Conteudo"])

    with pytest.raises(PdfTooLargeError):
        extract_pdf(content, max_size_bytes=1)

import pytest

from app.services.documents import (
    EmptyPdfError,
    InvalidPdfError,
    PdfTooLargeError,
    PdfTooManyPagesError,
    extract_pdf,
    sanitize_filename,
)
from tests.helpers import build_encrypted_pdf, build_pdf


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


def test_extract_rejects_pdf_with_opening_password() -> None:
    with pytest.raises(InvalidPdfError) as exc_info:
        extract_pdf(build_encrypted_pdf(["Conteudo"], user_password="leitor"))

    assert "senha" in exc_info.value.message


def test_extract_reads_pdf_protected_only_by_owner_password() -> None:
    result = extract_pdf(build_encrypted_pdf(["Conteudo liberado para leitura"], user_password=""))

    assert "Conteudo liberado para leitura" in result.pages[0].text


def test_extract_rejects_too_many_pages() -> None:
    with pytest.raises(PdfTooManyPagesError):
        extract_pdf(build_pdf(["1", "2", "3"]), max_pages=2)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("C:\\Users\\aluno\\Desktop\\aula.pdf", "aula.pdf"),
        ("../../etc/passwd", "passwd"),
        ("relatorio\u202efdp.exe", "relatoriofdp.exe"),
        ("nome\x00com\x07controle.pdf", "nomecomcontrole.pdf"),
        ("Matemática – Capítulo 1.pdf", "Matemática – Capítulo 1.pdf"),
        ("   ", "document.pdf"),
        ("..", "document.pdf"),
        (None, "document.pdf"),
    ],
)
def test_sanitize_filename(raw: str | None, expected: str) -> None:
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_limits_length_and_keeps_extension() -> None:
    sanitized = sanitize_filename("a" * 300 + ".pdf")

    assert len(sanitized) == 255
    assert sanitized.endswith(".pdf")

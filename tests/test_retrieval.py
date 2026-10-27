from app.schemas.documents import ExtractedDocument, ExtractedPage
from app.services.retrieval import format_context, retrieve_relevant_excerpts


def _document(*texts: str) -> ExtractedDocument:
    pages = [ExtractedPage(page_number=index, text=text) for index, text in enumerate(texts, start=1)]
    return ExtractedDocument(page_count=len(pages), pages=pages)


def test_retrieval_selects_relevant_pages() -> None:
    document = _document(
        "A fotossintese converte luz em energia quimica.",
        "A gravidade atrai corpos massivos.",
        "Mitose e um processo de divisao celular.",
    )

    pages = retrieve_relevant_excerpts(document, "Explique a fotossíntese com clareza")

    assert [page.page_number for page in pages] == [1]
    assert "fotossintese" in pages[0].text.lower() or "fotossíntese" in pages[0].text.lower() or "fotossintese" in pages[0].text


def test_retrieval_preserves_original_page_numbers() -> None:
    document = _document("Introducao geral", "O conceito de mitose aparece aqui", "Conclusao")

    pages = retrieve_relevant_excerpts(document, "O que é mitose?")

    assert pages[0].page_number == 2
    assert "mitose" in pages[0].text.lower()


def test_retrieval_fallback_when_there_is_no_clear_match() -> None:
    document = _document("Primeira pagina de apoio", "Segunda pagina de apoio", "Terceira pagina de apoio")

    pages = retrieve_relevant_excerpts(document, "xyzabc termo inexistente", max_excerpts=2)

    assert [page.page_number for page in pages] == [1, 2]


def test_format_context_keeps_page_labels() -> None:
    pages = [
        ExtractedPage(page_number=3, text="Trecho real da pagina tres"),
        ExtractedPage(page_number=5, text="Trecho real da pagina cinco"),
    ]

    context = format_context(pages)

    assert "[Página 3]" in context
    assert "[Página 5]" in context
    assert "Trecho real da pagina tres" in context

from app.schemas.documents import ExtractedDocument, ExtractedPage
from app.services.retrieval import (
    best_excerpt,
    format_context,
    query_terms,
    retrieve_from_documents,
    retrieve_pages,
    retrieve_relevant_excerpts,
)


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


def test_long_page_is_cut_to_the_budget_around_the_match() -> None:
    long_page = "introducao geral " * 600 + "A mitocondria produz energia para a celula. " + "conclusao " * 600
    document = _document(long_page)

    pages, has_match = retrieve_pages(document, "O que a mitocôndria produz?", max_chars=500)

    assert has_match is True
    assert len(pages[0].text) <= 500
    assert "mitocondria" in pages[0].text
    assert pages[0].text.startswith("[...]") and pages[0].text.endswith("[...]")


def test_total_context_never_exceeds_the_budget() -> None:
    document = _document(*[f"fotossintese pagina {index} " + "texto " * 400 for index in range(1, 4)])

    pages, _ = retrieve_pages(document, "fotossintese", max_excerpts=3, max_chars=1200)

    assert sum(len(page.text) for page in pages) <= 1200


def test_instruction_and_meta_words_do_not_drive_retrieval() -> None:
    document = _document(
        "Capitulo 1. Neste capitulo veremos o texto base do material.",
        "A fotossintese ocorre nos cloroplastos.",
    )

    pages, has_match = retrieve_pages(document, "Explique a fotossíntese deste capítulo do texto")

    assert has_match is True
    assert [page.page_number for page in pages] == [2]


def test_plural_and_accent_variants_match() -> None:
    document = _document("Introducao", "As células se dividem por mitose.", "As funções do núcleo.")

    assert [page.page_number for page in retrieve_relevant_excerpts(document, "o que é uma celula?")] == [2]
    assert [page.page_number for page in retrieve_relevant_excerpts(document, "qual a função do nucleo")] == [3]


def test_ties_prefer_pages_with_more_occurrences() -> None:
    document = _document("A mitose aparece uma vez.", "Mitose, mitose e mais mitose.")

    pages, _ = retrieve_pages(document, "mitose", max_excerpts=2)

    assert [page.page_number for page in pages] == [2, 1]


def test_question_with_only_generic_words_falls_back_to_first_pages() -> None:
    document = _document("Primeira pagina", "Segunda pagina", "Terceira pagina", "Quarta pagina")

    pages, has_match = retrieve_pages(document, "Resuma o texto", max_excerpts=2)

    assert query_terms("Resuma o texto") == set()
    assert has_match is False
    assert [page.page_number for page in pages] == [1, 2]


def test_duplicate_pages_are_sent_once() -> None:
    document = _document("Cabecalho repetido sobre mitose", "Cabecalho repetido sobre mitose", "Mitose de novo aqui")

    pages, _ = retrieve_pages(document, "mitose", max_excerpts=3)

    assert [page.page_number for page in pages] == [1, 3]


def test_best_excerpt_is_centered_on_the_terms_and_bounded() -> None:
    text = "palavra " * 200 + "O ribossomo sintetiza proteinas. " + "palavra " * 200

    excerpt = best_excerpt(text, query_terms("ribossomo"), 120)

    assert "ribossomo" in excerpt
    assert len(excerpt) <= 120


def test_retrieval_searches_only_the_provided_documents() -> None:
    attached = _document("A mitose divide celulas.")
    other = _document("A fotossintese ocorre nos cloroplastos.")

    pages, has_match = retrieve_from_documents(
        [("doc-mitose", "aula.pdf", attached), ("doc-foto", "outro.pdf", other)],
        "Onde ocorre a fotossintese?",
        max_excerpts=1,
    )

    assert has_match is True
    assert pages[0].document_id == "doc-foto"
    assert pages[0].page_number == 1

    only_attached, no_match = retrieve_from_documents(
        [("doc-mitose", "aula.pdf", attached)],
        "Onde ocorre a fotossintese?",
        max_excerpts=1,
    )
    assert no_match is False
    assert only_attached[0].document_id == "doc-mitose"

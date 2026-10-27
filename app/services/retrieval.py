"""Recuperação lexical de páginas relevantes, sem embeddings nem banco vetorial."""

from __future__ import annotations

import re
import unicodedata

from app.schemas.documents import ExtractedDocument, ExtractedPage

STOPWORDS = {
    "a",
    "ao",
    "aos",
    "as",
    "ate",
    "com",
    "como",
    "da",
    "das",
    "de",
    "dela",
    "dele",
    "deles",
    "depois",
    "do",
    "dos",
    "e",
    "ela",
    "elas",
    "ele",
    "eles",
    "em",
    "entre",
    "era",
    "essa",
    "esse",
    "esta",
    "este",
    "eu",
    "foi",
    "for",
    "foram",
    "isso",
    "isto",
    "ja",
    "lhe",
    "mais",
    "mas",
    "me",
    "mesmo",
    "meu",
    "minha",
    "muito",
    "na",
    "nas",
    "nem",
    "no",
    "nos",
    "o",
    "os",
    "ou",
    "para",
    "pela",
    "pelas",
    "pelo",
    "pelos",
    "por",
    "qual",
    "quando",
    "que",
    "quem",
    "se",
    "sem",
    "seu",
    "sua",
    "sao",
    "tambem",
    "te",
    "tem",
    "ter",
    "teu",
    "um",
    "uma",
    "voce",
}


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    without_accents = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return without_accents.lower()


def tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize_text(value))


def query_terms(query: str) -> set[str]:
    return {token for token in tokenize(query) if token not in STOPWORDS and len(token) > 1}


def retrieve_relevant_excerpts(
    document: ExtractedDocument,
    query: str,
    *,
    max_excerpts: int = 3,
    max_chars: int = 6000,
) -> list[ExtractedPage]:
    """Seleciona páginas relevantes pela sobreposição de termos com a pergunta."""
    terms = query_terms(query)
    scored: list[tuple[int, ExtractedPage]] = []
    for page in document.pages:
        if not page.text.strip():
            continue
        page_tokens = set(tokenize(page.text))
        score = len(terms & page_tokens) if terms else 0
        scored.append((score, page))

    if not scored:
        return []

    matched = [page for score, page in scored if score > 0]
    if matched:
        matched.sort(key=lambda page: (-_score(page, terms), page.page_number))
        selected = matched[:max_excerpts]
    else:
        selected = [page for _, page in scored][:max_excerpts]

    return _limit_chars(selected, max_chars)


def format_context(pages: list[ExtractedPage]) -> str:
    blocks: list[str] = []
    for page in pages:
        text = page.text.strip()
        if not text:
            continue
        blocks.append(f"[Página {page.page_number}]\n{text}")
    return "\n\n".join(blocks)


def _score(page: ExtractedPage, terms: set[str]) -> int:
    return len(terms & set(tokenize(page.text)))


def _limit_chars(pages: list[ExtractedPage], max_chars: int) -> list[ExtractedPage]:
    selected: list[ExtractedPage] = []
    used = 0
    for page in pages:
        size = len(page.text)
        if selected and used + size > max_chars:
            break
        selected.append(page)
        used += size
        if used >= max_chars:
            break
    return selected or pages[:1]

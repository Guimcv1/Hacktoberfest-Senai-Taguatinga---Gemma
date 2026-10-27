"""Recuperação lexical de páginas relevantes, sem embeddings nem banco vetorial."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

from dataclasses import dataclass

from app.schemas.documents import ExtractedDocument, ExtractedPage

# Palavras funcionais, verbos de comando e referências ao próprio material ("explique este
# capítulo do texto") não indicam o assunto da pergunta e distorcem a ordem das páginas.
STOPWORDS = {
    "a", "ainda", "alem", "algum", "alguma", "algumas", "alguns", "ao", "aos", "apenas", "aquela",
    "aquelas", "aquele", "aqueles", "aquilo", "as", "assim", "ate", "cada", "com", "como", "contra",
    "da", "daquela", "daquele", "das", "de", "dela", "dele", "deles", "depois", "desde", "desta",
    "destas", "deste", "destes", "disso", "disto", "do", "dos", "e", "ela", "elas", "ele", "eles",
    "em", "entre", "era", "essa", "essas", "esse", "esses", "esta", "estao", "estas", "estava",
    "estavam", "este", "estes", "eu", "foi", "for", "foram", "ha", "havia", "isso", "isto", "ja",
    "la", "lhe", "mais", "mas", "me", "mesmo", "meu", "minha", "muito", "na", "nao", "nas", "nela",
    "nelas", "nele", "neles", "nem", "nesta", "nestas", "neste", "nestes", "nisso", "nisto", "no",
    "nos", "num", "numa", "o", "onde", "os", "ou", "outra", "outras", "outro", "outros", "para",
    "pela", "pelas", "pelo", "pelos", "pode", "podem", "pois", "por", "porque", "qual", "quais",
    "quando", "quanto", "quantos", "que", "quem", "sao", "se", "seja", "sem", "ser", "seu", "sim",
    "so", "sob", "sobre", "sua", "tal", "tambem", "te", "tem", "ter", "teu", "toda", "todas", "todo",
    "todos", "tudo", "um", "uma", "voce",
    "cite", "compare", "comparar", "conceito", "defina", "definicao", "definir", "descreva",
    "descrever", "diga", "dizer", "exemplo", "explica", "explicacao", "explicar", "explique",
    "fale", "falar", "liste", "listar", "mostre", "mostrar", "resuma", "resumir", "resumo",
    "significa", "significado",
    "arquivo", "assunto", "capitulo", "conteudo", "documento", "material", "pagina", "pdf",
    "tema", "texto", "topico", "trecho",
}

_WORD = re.compile(r"\w+")
_SPACE = re.compile(r"\s")
_PLURAL_SUFFIXES = (("oes", "ao"), ("aes", "ao"), ("ais", "al"), ("ns", "m"), ("res", "r"), ("zes", "z"))
_MIN_TRUNCATED_CHARS = 200
_TRUNCATION_MARK = "[...]"


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFD", value)
    without_accents = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    return without_accents.lower()


def tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", normalize_text(value))


def stem(token: str) -> str:
    """Reduz plurais comuns do português (células -> celula, funções -> funcao)."""
    if len(token) <= 3 or not token.endswith("s"):
        return token
    for suffix, replacement in _PLURAL_SUFFIXES:
        if token.endswith(suffix) and len(token) - len(suffix) >= 2:
            return token[: -len(suffix)] + replacement
    return token[:-1]


def query_terms(query: str) -> set[str]:
    terms: set[str] = set()
    for token in tokenize(query):
        if len(token) < 2 or token in STOPWORDS:
            continue
        stemmed = stem(token)
        if stemmed not in STOPWORDS:
            terms.add(stemmed)
    return terms


@dataclass(frozen=True)
class RetrievedExcerpt:
    page_number: int
    text: str
    document_id: str = ""
    filename: str = ""


def retrieve_pages(
    document: ExtractedDocument,
    query: str,
    *,
    max_excerpts: int = 3,
    max_chars: int = 6000,
) -> tuple[list[ExtractedPage], bool]:
    """Seleciona páginas relevantes dentro de max_chars. O segundo valor indica correspondência lexical."""
    excerpts, has_match = retrieve_from_documents(
        [("", "", document)],
        query,
        max_excerpts=max_excerpts,
        max_chars=max_chars,
    )
    return [ExtractedPage(page_number=item.page_number, text=item.text) for item in excerpts], has_match


def retrieve_from_documents(
    documents: list[tuple[str, str, ExtractedDocument]],
    query: str,
    *,
    max_excerpts: int = 3,
    max_chars: int = 6000,
) -> tuple[list[RetrievedExcerpt], bool]:
    """Recupera trechos só dos documentos informados (os associados à conversa)."""
    terms = query_terms(query)
    candidates: list[tuple[RetrievedExcerpt, Counter[str]]] = []
    seen_text: set[str] = set()
    for document_id, filename, document in documents:
        for page in document.pages:
            normalized = " ".join(page.text.split())
            if not normalized or normalized in seen_text:
                continue
            seen_text.add(normalized)
            excerpt = RetrievedExcerpt(
                page_number=page.page_number,
                text=page.text,
                document_id=document_id,
                filename=filename,
            )
            candidates.append((excerpt, Counter(stem(token) for token in tokenize(page.text))))

    if not candidates:
        return [], False

    matched: list[tuple[int, int, RetrievedExcerpt]] = []
    for excerpt, counts in candidates:
        distinct = sum(1 for term in terms if counts[term])
        if distinct:
            matched.append((distinct, sum(counts[term] for term in terms), excerpt))

    if matched:
        matched.sort(key=lambda item: (-item[0], -item[1], item[2].page_number, item[2].filename))
        selected = [excerpt for _, _, excerpt in matched[:max_excerpts]]
    else:
        selected = [excerpt for excerpt, _ in candidates[:max_excerpts]]

    return _fit_to_budget(selected, terms, max_chars), bool(matched)


def retrieve_relevant_excerpts(
    document: ExtractedDocument,
    query: str,
    *,
    max_excerpts: int = 3,
    max_chars: int = 6000,
) -> list[ExtractedPage]:
    """Seleciona páginas relevantes pela sobreposição de termos com a pergunta."""
    pages, _has_match = retrieve_pages(
        document,
        query,
        max_excerpts=max_excerpts,
        max_chars=max_chars,
    )
    return pages


def format_context(pages: list[ExtractedPage] | list[RetrievedExcerpt]) -> str:
    document_ids = {getattr(page, "document_id", "") or "" for page in pages}
    use_filename = len([item for item in document_ids if item]) > 1
    blocks: list[str] = []
    for page in pages:
        text = page.text.strip()
        if not text:
            continue
        filename = getattr(page, "filename", "") or ""
        label = (
            f"[Página {page.page_number} — {filename}]"
            if use_filename and filename
            else f"[Página {page.page_number}]"
        )
        blocks.append(f"{label}\n{text}")
    return "\n\n".join(blocks)


def best_excerpt(text: str, terms: set[str], max_chars: int) -> str:
    """Janela de até max_chars com o maior número de ocorrências dos termos (ou o início)."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    start, end = _window(text, terms, max_chars)
    return text[start:end].strip()


def _window(text: str, terms: set[str], max_chars: int) -> tuple[int, int]:
    positions = [match.start() for match in _WORD.finditer(text) if _matches_terms(match.group(), terms)]
    start = 0
    if positions:
        span = max_chars * 3 // 4
        best_left, best_count, left = 0, 0, 0
        for right, position in enumerate(positions):
            while position - positions[left] > span:
                left += 1
            if right - left + 1 > best_count:
                best_left, best_count = left, right - left + 1
        start = positions[best_left] - (max_chars - span) // 2
    start = max(0, min(start, len(text) - max_chars))
    if start > 0:
        boundary = _SPACE.search(text, start, start + 40)
        if boundary is not None:
            start = boundary.end()

    end = min(len(text), start + max_chars)
    if end < len(text):
        spaces = [match.start() for match in _SPACE.finditer(text, start, end)]
        if spaces and spaces[-1] > start + max_chars * 0.6:
            end = spaces[-1]
    return start, end


def _matches_terms(word: str, terms: set[str]) -> bool:
    return bool(terms) and any(stem(token) in terms for token in tokenize(word))


def _truncate_for_context(text: str, terms: set[str], max_chars: int) -> str:
    start, end = _window(text, terms, max(max_chars - 2 * (len(_TRUNCATION_MARK) + 1), 1))
    excerpt = text[start:end].strip()
    if start > 0:
        excerpt = f"{_TRUNCATION_MARK} {excerpt}"
    if end < len(text):
        excerpt = f"{excerpt} {_TRUNCATION_MARK}"
    return excerpt


def _fit_to_budget(pages: list[RetrievedExcerpt], terms: set[str], max_chars: int) -> list[RetrievedExcerpt]:
    fitted: list[RetrievedExcerpt] = []
    remaining = max_chars
    for page in pages:
        text = page.text.strip()
        if len(text) > remaining:
            if fitted and remaining < _MIN_TRUNCATED_CHARS:
                break
            text = _truncate_for_context(text, terms, remaining)
        fitted.append(
            RetrievedExcerpt(
                page_number=page.page_number,
                text=text,
                document_id=page.document_id,
                filename=page.filename,
            )
        )
        remaining -= len(text)
        if remaining <= 0:
            break
    return fitted

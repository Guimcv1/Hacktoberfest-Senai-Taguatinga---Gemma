"""Contexto de estudo compartilhado entre chat e geração de questões."""

from __future__ import annotations

from app.core.config import Settings
from app.db.models import Document
from app.schemas.chat import ChatSource
from app.services.document_repo import extracted_from_row
from app.services.retrieval import best_excerpt, format_context, query_terms, retrieve_from_documents

_MAX_EXCERPT_CHARS = 400


def document_context(
    documents: list[Document],
    query: str,
    settings: Settings,
) -> tuple[str, bool, list[ChatSource]]:
    if not documents:
        return "", False, []
    corpus = [(document.id, document.filename, extracted_from_row(document)) for document in documents]
    pages, has_match = retrieve_from_documents(
        corpus,
        query,
        max_excerpts=settings.max_retrieval_pages,
        max_chars=settings.max_context_chars,
    )
    terms = query_terms(query)
    context = format_context(pages)
    sources: list[ChatSource] = []
    if has_match:
        sources = [
            ChatSource(
                page=page.page_number,
                excerpt=best_excerpt(" ".join(page.text.split()), terms, _MAX_EXCERPT_CHARS),
                document_id=page.document_id or None,
                filename=page.filename or None,
            )
            for page in pages
        ]
    return context, has_match, sources

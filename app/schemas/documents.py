from datetime import datetime

from pydantic import BaseModel, Field


class ExtractedPage(BaseModel):
    page_number: int = Field(ge=1, description="Número da página, começando em 1.")
    text: str = Field(description="Texto extraído da página.")


class ExtractedDocument(BaseModel):
    page_count: int = Field(ge=1, description="Quantidade de páginas do PDF.")
    pages: list[ExtractedPage]


class DocumentUploadResponse(BaseModel):
    document_id: str = Field(description="Identificador gerado para o documento processado.")
    filename: str = Field(description="Nome do arquivo enviado.")
    page_count: int = Field(ge=1, description="Quantidade de páginas do PDF.")
    pages: list[ExtractedPage]
    deduplicated: bool = False
    conversation_id: str | None = Field(default=None, description="Conversa à qual o PDF foi anexado, se informada.")


class DocumentMeta(BaseModel):
    document_id: str
    filename: str
    page_count: int
    text_chars: int
    created_at: datetime
    expires_at: datetime


class DocumentDetail(DocumentMeta):
    pages: list[ExtractedPage]


class DocumentListResponse(BaseModel):
    items: list[DocumentMeta]
    total: int
    limit: int
    offset: int

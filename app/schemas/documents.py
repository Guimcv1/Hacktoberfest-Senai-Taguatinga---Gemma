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

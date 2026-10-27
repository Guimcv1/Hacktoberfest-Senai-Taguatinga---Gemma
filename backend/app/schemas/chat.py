from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.ids import optional_id, optional_id_field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="Pergunta do estudante.")
    conversation_id: str | None = optional_id_field(
        "Conversa existente; se omitido, uma nova é criada. Não é obrigatório ter PDF."
    )
    document_id: str | None = optional_id_field(
        "PDF opcional a associar nesta mensagem. Sem ele, a IA usa o histórico e os PDFs já anexados."
    )

    @field_validator("document_id", "conversation_id", mode="before")
    @classmethod
    def blank_as_none(cls, value: object) -> object:
        return optional_id(value)


class ChatSource(BaseModel):
    page: int = Field(ge=1, description="Número original da página recuperada.")
    excerpt: str = Field(description="Trecho real extraído da página.")
    document_id: str | None = Field(default=None, description="Documento de origem do trecho.")
    filename: str | None = Field(default=None, description="Nome do arquivo de origem.")


class ChatResponse(BaseModel):
    conversation_id: str
    document_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    answer: str
    sources: list[ChatSource]
    model: str
    status: Literal["completed"] = "completed"
    has_relevant_match: bool = False
    used_documents: bool = False


class ConversationCreate(BaseModel):
    document_id: str | None = optional_id_field("PDF opcional. Omita para criar a conversa sem material.")
    title: str | None = Field(default=None, max_length=200, json_schema_extra={"default": None})

    @field_validator("document_id", mode="before")
    @classmethod
    def blank_as_none(cls, value: object) -> object:
        return optional_id(value)


class ConversationDocumentAttach(BaseModel):
    document_id: str = Field(min_length=1)


class ConversationSummary(BaseModel):
    id: str
    document_id: str | None = None
    document_ids: list[str] = Field(default_factory=list)
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int


class ConversationListResponse(BaseModel):
    items: list[ConversationSummary]
    total: int
    limit: int
    offset: int


class ConversationMessage(BaseModel):
    id: str
    role: str
    content: str
    sources: list[ChatSource] | None = None
    model: str | None = None
    created_at: datetime


class ConversationDetail(ConversationSummary):
    messages: list[ConversationMessage]

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    document_id: str = Field(min_length=1, description="Identificador retornado no upload.")
    message: str = Field(min_length=1, description="Pergunta do estudante.")
    conversation_id: str | None = Field(default=None, description="Conversa existente; se omitido, uma nova é criada.")


class ChatSource(BaseModel):
    page: int = Field(ge=1, description="Número original da página recuperada.")
    excerpt: str = Field(description="Trecho real extraído da página.")


class ChatResponse(BaseModel):
    document_id: str
    conversation_id: str
    answer: str
    sources: list[ChatSource]
    model: str
    status: Literal["completed"] = "completed"
    has_relevant_match: bool = True


class ConversationCreate(BaseModel):
    document_id: str = Field(min_length=1)
    title: str | None = Field(default=None, max_length=200)


class ConversationSummary(BaseModel):
    id: str
    document_id: str
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

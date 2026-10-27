from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    document_id: str = Field(min_length=1, description="Identificador retornado no upload.")
    message: str = Field(min_length=1, description="Pergunta do estudante.")


class ChatSource(BaseModel):
    page: int = Field(ge=1, description="Número original da página recuperada.")
    excerpt: str = Field(description="Trecho real extraído da página.")


class ChatResponse(BaseModel):
    document_id: str
    answer: str
    sources: list[ChatSource]
    model: str

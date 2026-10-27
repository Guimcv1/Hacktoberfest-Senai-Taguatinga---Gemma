from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="Estado de saúde do backend.")
    service: str = Field(description="Nome do serviço.")


class ReadyResponse(BaseModel):
    status: Literal["ok", "degraded"] = Field(description="degraded (HTTP 503) se o banco falhar ou faltar migração.")
    database: Literal["ok", "error"]
    migrations: Literal["ok", "pending", "unknown"]
    ai_configured: bool = Field(description="Se AI_BASE_URL está definido. A URL nunca é exposta.")
    ai: Literal["not_checked", "ok", "unreachable", "not_configured"] = Field(
        description="Resultado de GET na raiz do Ollama, apenas com check_ai=true. Não afeta o status."
    )

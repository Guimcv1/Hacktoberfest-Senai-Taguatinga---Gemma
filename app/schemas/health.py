from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(description="Estado de saúde do backend.")
    service: str = Field(description="Nome do serviço.")


class ReadyResponse(BaseModel):
    status: str
    database: str
    ai_configured: bool

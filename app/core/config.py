from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações lidas do ambiente. O endereço da IA não fica hardcoded."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "StudyBuddy AI"
    ai_base_url: str = ""
    ai_model: str = "gemma3:4b"
    ai_timeout_seconds: float = Field(default=120.0, gt=0)
    max_pdf_size_mb: int = Field(default=10, ge=1)
    document_ttl_minutes: int = Field(default=30, ge=1)
    max_stored_documents: int = Field(default=50, ge=1)
    max_stored_text_chars: int = Field(default=400_000, ge=1000)
    max_chat_message_chars: int = Field(default=2000, ge=50)
    max_retrieval_pages: int = Field(default=3, ge=1)
    max_context_chars: int = Field(default=6000, ge=200)

    @property
    def max_pdf_size_bytes(self) -> int:
        return self.max_pdf_size_mb * 1024 * 1024

    @property
    def document_ttl_seconds(self) -> int:
        return self.document_ttl_minutes * 60


@lru_cache
def get_settings() -> Settings:
    return Settings()

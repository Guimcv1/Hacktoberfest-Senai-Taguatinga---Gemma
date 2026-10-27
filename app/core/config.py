import os
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações lidas do ambiente. Segredos não ficam hardcoded."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "StudyBuddy AI"
    environment: str = "development"
    ai_base_url: str = ""
    ai_model: str = "gemma3:4b"
    ai_timeout_seconds: float = Field(default=120.0, gt=0)
    database_url: str = "sqlite:///./data/studybuddy.db"
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = Field(default=480, ge=5)
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    max_pdf_size_mb: int = Field(default=10, ge=1)
    max_pdf_pages: int = Field(default=50, ge=1)
    document_ttl_minutes: int = Field(default=30, ge=1)
    max_stored_documents: int = Field(default=50, ge=1)
    max_stored_text_chars: int = Field(default=400_000, ge=1000)
    max_chat_message_chars: int = Field(default=2000, ge=50)
    max_retrieval_pages: int = Field(default=3, ge=1)
    max_context_chars: int = Field(default=6000, ge=200)
    rate_limit_per_minute: int = Field(default=60, ge=5)

    @property
    def max_pdf_size_bytes(self) -> int:
        return self.max_pdf_size_mb * 1024 * 1024

    @property
    def document_ttl_seconds(self) -> int:
        return self.document_ttl_minutes * 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @field_validator("environment")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        return value.lower().strip()


def env_file_path() -> str | None:
    """APP_ENV_FILE vazio desativa a leitura de arquivo (usado pelos testes)."""
    return os.getenv("APP_ENV_FILE", ".env") or None


@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=env_file_path())

import os
import re
from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = "sqlite:///./data/studybuddy.db"
DEFAULT_OLLAMA_KEEP_ALIVE = "120s"
# Tag oficial na biblioteca do Ollama: https://ollama.com/library/gemma4:e4b
DEFAULT_AI_MODEL = "gemma4:e4b"
# Durações aceitas pelo UnmarshalJSON do Ollama (time.ParseDuration).
_OLLAMA_DURATION = re.compile(r"^(?:\d+(?:\.\d+)?(?:ns|us|µs|ms|s|m|h))+$")

# Valores que já foram publicados no repositório e nunca podem assinar tokens reais.
_PUBLIC_PLACEHOLDER_SECRETS = {
    "substitua-por-um-segredo-com-pelo-menos-32-chars",
    "migration-placeholder-secret-key-32",
    "test-jwt-secret-key-32-chars-minimum",
}

_BASE_CONFIG = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
    case_sensitive=False,
    hide_input_in_errors=True,
)


class ConfigurationError(RuntimeError):
    """Configuração ausente ou inválida; a mensagem nunca inclui os valores informados."""


class Settings(BaseSettings):
    """Configurações lidas do ambiente. Segredos não ficam hardcoded."""

    model_config = _BASE_CONFIG

    app_name: str = "StudyBuddy AI"
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    ai_base_url: str = ""
    ai_model: str = DEFAULT_AI_MODEL
    ai_timeout_seconds: float = Field(default=120.0, gt=0)
    ollama_keep_alive: str = Field(
        default=DEFAULT_OLLAMA_KEEP_ALIVE,
        description="Quanto tempo o Ollama mantém o modelo na memória após a última resposta.",
    )
    database_url: str = DEFAULT_DATABASE_URL
    db_auto_migrate: bool = True
    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    jwt_expires_minutes: int = Field(default=480, ge=5)
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://127.0.0.1:3000"
    max_pdf_size_mb: int = Field(default=10, ge=1)
    max_pdf_pages: int = Field(default=50, ge=1)
    document_ttl_minutes: int = Field(default=10_080, ge=1)
    max_stored_documents: int = Field(default=50, ge=1)
    max_stored_text_chars: int = Field(default=2_000_000, ge=1000)
    document_storage_dir: str = Field(
        default="./data/documents",
        description="Diretório local dos PDFs originais. No Docker: /data/documents.",
    )
    max_chat_message_chars: int = Field(default=2000, ge=50)
    max_retrieval_pages: int = Field(default=3, ge=1)
    max_context_chars: int = Field(default=6000, ge=200)
    rate_limit_per_minute: int = Field(default=60, ge=0)
    rate_limit_auth_per_minute: int = Field(default=20, ge=0)

    @property
    def max_pdf_size_bytes(self) -> int:
        return self.max_pdf_size_mb * 1024 * 1024

    @property
    def document_ttl_seconds(self) -> int:
        return self.document_ttl_minutes * 60

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip().rstrip("/") for item in self.cors_origins.split(",") if item.strip()]

    @field_validator("environment", mode="before")
    @classmethod
    def normalize_environment(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value().strip()
        if len(secret) < 32:
            raise ValueError("defina um segredo aleatório com pelo menos 32 caracteres.")
        if secret.lower() in _PUBLIC_PLACEHOLDER_SECRETS:
            raise ValueError("o valor é um exemplo público; gere um segredo novo.")
        return value

    @field_validator("ollama_keep_alive", mode="before")
    @classmethod
    def validate_ollama_keep_alive(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("use uma duração do Ollama, por exemplo 120s, 2m, 0 ou -1.")
        if isinstance(value, (int, float)):
            if value in {-1, 0}:
                return str(int(value))
            if value > 0 and float(value) == int(value):
                return f"{int(value)}s"
            raise ValueError("use uma duração do Ollama, por exemplo 120s, 2m, 0 ou -1.")
        if not isinstance(value, str):
            return value
        value = value.strip()
        if value in {"-1", "0"}:
            return value
        if value.isdigit() and int(value) > 0:
            return f"{int(value)}s"
        if _OLLAMA_DURATION.fullmatch(value):
            return value
        raise ValueError("use uma duração do Ollama, por exemplo 120s, 2m, 0 ou -1.")

    @field_validator("document_storage_dir", mode="before")
    @classmethod
    def validate_document_storage_dir(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            raise ValueError("defina o diretório de armazenamento dos PDFs.")
        return value

    @field_validator("ai_model", mode="before")
    @classmethod
    def validate_ai_model(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            raise ValueError("defina a tag do modelo no Ollama, por exemplo gemma4:e4b.")
        return value

    @field_validator("ai_base_url")
    @classmethod
    def validate_ai_base_url(cls, value: str) -> str:
        value = value.strip().rstrip("/")
        if not value:
            return ""
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("use uma URL completa iniciada por http:// ou https://.")
        return value

    @model_validator(mode="after")
    def validate_production(self) -> "Settings":
        if self.environment == "production" and "*" in self.cors_origin_list:
            raise ValueError("CORS_ORIGINS não pode conter * em produção.")
        return self


class DatabaseSettings(BaseSettings):
    """Subconjunto usado por ferramentas (Alembic) que não precisam dos segredos da API."""

    model_config = _BASE_CONFIG

    database_url: str = DEFAULT_DATABASE_URL


def env_file_path() -> str | None:
    """APP_ENV_FILE vazio desativa a leitura de arquivo (usado pelos testes)."""
    return os.getenv("APP_ENV_FILE", ".env") or None


def describe_validation_error(exc: ValidationError) -> str:
    lines = ["Configuração inválida. Revise as variáveis de ambiente ou o arquivo .env:"]
    for error in exc.errors(include_url=False, include_input=False, include_context=False):
        field = ".".join(str(part) for part in error["loc"]).upper() or "CONFIGURAÇÃO"
        if error["type"] == "missing":
            message = "variável obrigatória não definida."
        else:
            message = error["msg"].removeprefix("Value error, ")
        lines.append(f"- {field}: {message}")
    return "\n".join(lines)


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings(_env_file=env_file_path())
    except ValidationError as exc:
        raise ConfigurationError(describe_validation_error(exc)) from None


def get_database_url() -> str:
    try:
        return DatabaseSettings(_env_file=env_file_path()).database_url
    except ValidationError as exc:
        raise ConfigurationError(describe_validation_error(exc)) from None

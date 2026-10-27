import pytest

from app.core.config import (
    DEFAULT_AI_MODEL,
    DEFAULT_OLLAMA_KEEP_ALIVE,
    ConfigurationError,
    Settings,
    get_database_url,
    get_settings,
)

VALID_SECRET = "a-valid-random-secret-with-more-than-32-chars"


@pytest.fixture
def fresh_settings(monkeypatch: pytest.MonkeyPatch):
    get_settings.cache_clear()
    yield monkeypatch
    get_settings.cache_clear()


def _settings(**overrides) -> Settings:
    values = {"jwt_secret": VALID_SECRET, **overrides}
    return Settings(_env_file=None, **values)


def test_missing_jwt_secret_fails_with_friendly_message(fresh_settings: pytest.MonkeyPatch) -> None:
    fresh_settings.delenv("JWT_SECRET", raising=False)

    with pytest.raises(ConfigurationError) as exc_info:
        get_settings()

    assert "JWT_SECRET" in str(exc_info.value)
    assert "não definida" in str(exc_info.value)


def test_short_jwt_secret_is_rejected_without_echoing_it(fresh_settings: pytest.MonkeyPatch) -> None:
    fresh_settings.setenv("JWT_SECRET", "curto-demais-123")

    with pytest.raises(ConfigurationError) as exc_info:
        get_settings()

    assert "JWT_SECRET" in str(exc_info.value)
    assert "curto-demais-123" not in str(exc_info.value)


@pytest.mark.parametrize(
    "placeholder",
    ["substitua-por-um-segredo-com-pelo-menos-32-chars", "migration-placeholder-secret-key-32"],
)
def test_published_placeholder_secrets_are_rejected(fresh_settings: pytest.MonkeyPatch, placeholder: str) -> None:
    fresh_settings.setenv("JWT_SECRET", placeholder)

    with pytest.raises(ConfigurationError) as exc_info:
        get_settings()

    assert "exemplo público" in str(exc_info.value)
    assert placeholder not in str(exc_info.value)


def test_secret_is_not_exposed_in_repr() -> None:
    settings = _settings()

    assert VALID_SECRET not in repr(settings)
    assert VALID_SECRET not in str(settings.model_dump())
    assert settings.jwt_secret.get_secret_value() == VALID_SECRET


@pytest.mark.parametrize("algorithm", ["none", "RS256", "hs256"])
def test_only_hmac_jwt_algorithms_are_accepted(algorithm: str) -> None:
    with pytest.raises(ValueError):
        _settings(jwt_algorithm=algorithm)


def test_environment_is_normalized_and_validated() -> None:
    assert _settings(environment=" Production ").environment == "production"
    with pytest.raises(ValueError):
        _settings(environment="prod")


def test_document_storage_dir_has_local_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DOCUMENT_STORAGE_DIR", raising=False)
    assert _settings().document_storage_dir == "./data/documents"
    with pytest.raises(ValueError):
        _settings(document_storage_dir="  ")


def test_default_ai_model_is_official_gemma4_e4b() -> None:
    assert DEFAULT_AI_MODEL == "gemma4:e4b"
    assert _settings().ai_model == "gemma4:e4b"


def test_ai_model_can_be_overridden(fresh_settings: pytest.MonkeyPatch) -> None:
    fresh_settings.setenv("JWT_SECRET", VALID_SECRET)
    fresh_settings.setenv("AI_MODEL", "gemma4:e4b-it-q8_0")
    assert get_settings().ai_model == "gemma4:e4b-it-q8_0"


def test_blank_ai_model_is_rejected() -> None:
    with pytest.raises(ValueError):
        _settings(ai_model="  ")


def test_ollama_keep_alive_defaults_to_two_minutes() -> None:
    assert DEFAULT_OLLAMA_KEEP_ALIVE == "120s"
    assert _settings().ollama_keep_alive == "120s"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("120s", "120s"), ("2m", "2m"), ("0", "0"), ("-1", "-1"), (120, "120s"), ("90", "90s")],
)
def test_ollama_keep_alive_accepts_ollama_durations(raw: object, expected: str) -> None:
    assert _settings(ollama_keep_alive=raw).ollama_keep_alive == expected


@pytest.mark.parametrize("invalid", ["", "forever", "-5s", True, -2, 1.5])
def test_ollama_keep_alive_rejects_invalid_values(invalid: object) -> None:
    with pytest.raises(ValueError):
        _settings(ollama_keep_alive=invalid)


def test_jwt_secret_remains_required_when_keep_alive_is_set(fresh_settings: pytest.MonkeyPatch) -> None:
    fresh_settings.delenv("JWT_SECRET", raising=False)
    fresh_settings.setenv("OLLAMA_KEEP_ALIVE", "120s")

    with pytest.raises(ConfigurationError) as exc_info:
        get_settings()

    assert "JWT_SECRET" in str(exc_info.value)


def test_ai_base_url_requires_scheme_and_drops_trailing_slash() -> None:
    assert _settings(ai_base_url="http://localhost:11434/").ai_base_url == "http://localhost:11434"
    assert _settings(ai_base_url="").ai_base_url == ""
    with pytest.raises(ValueError):
        _settings(ai_base_url="localhost:11434")


def test_wildcard_cors_is_rejected_in_production() -> None:
    assert _settings(environment="development", cors_origins="*").cors_origin_list == ["*"]
    with pytest.raises(ValueError):
        _settings(environment="production", cors_origins="*")


def test_cors_origins_ignore_trailing_slash() -> None:
    settings = _settings(cors_origins="http://localhost:5173/, https://app.example.com ,")

    assert settings.cors_origin_list == ["http://localhost:5173", "https://app.example.com"]


def test_env_file_is_read_only_when_configured(fresh_settings: pytest.MonkeyPatch, tmp_path) -> None:
    env_file = tmp_path / "custom.env"
    env_file.write_text("MAX_PDF_SIZE_MB=3\n", encoding="utf-8")
    fresh_settings.setenv("JWT_SECRET", VALID_SECRET)
    fresh_settings.delenv("MAX_PDF_SIZE_MB", raising=False)

    fresh_settings.setenv("APP_ENV_FILE", str(env_file))
    assert get_settings().max_pdf_size_mb == 3

    get_settings.cache_clear()
    fresh_settings.setenv("APP_ENV_FILE", "")
    assert get_settings().max_pdf_size_mb == 10


def test_database_url_does_not_require_api_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JWT_SECRET", raising=False)
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./migracao.db")

    assert get_database_url() == "sqlite:///./migracao.db"

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://abc:abc@localhost:5432/call_intelligence"
    cors_origins: str = "http://localhost:4200"

    # AI analysis. When no Anthropic credentials are available the rule-based analyzer is used.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-5-5"
    ai_engine: str = "auto"  # auto | claude | rules

    # Speech-to-text for uploaded recordings (requires requirements-transcription.txt).
    whisper_model: str = "base"
    upload_dir: str = "uploads"
    max_upload_mb: int = 50

    seed_on_startup: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()

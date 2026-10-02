from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8")
    database_url: str


# Cached settings instance to avoid reloading from disk on every access.
@lru_cache
def get_settings() -> Settings:
    """Return the application settings."""
    return Settings()  # pyright: ignore[reportCallIssue]

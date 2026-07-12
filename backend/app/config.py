"""
Application configuration via environment variables.

Uses pydantic-settings to load from .env file or environment.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Azure Speech Service ---
    azure_speech_key: str = ""
    azure_speech_region: str = "centralindia"

    # --- OpenAI ---
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # --- Whisper ---
    whisper_model: str = "small.en"

    # --- Audio validation ---
    max_upload_size_mb: int = 20
    min_duration_s: int = 30
    max_duration_s: int = 45

    # --- Scoring ---
    word_score_threshold: int = 80

    # --- Rate limiting ---
    rate_limit: str = "5/minute"

    # --- CORS ---
    allowed_origins: str = "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()

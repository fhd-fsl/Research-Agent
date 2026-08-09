"""Application settings, loaded from environment variables and .env file.

All configuration that varies between environments (API keys, feature flags,
defaults) lives here. Access via get_settings() to get a cached singleton.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM Provider API Keys ---
    gemini_api_key: str = ""
    groq_api_key: str = ""
    cerebras_api_key: str = ""
    openrouter_api_key: str = ""

    # --- Search API Keys ---
    tavily_api_key: str = ""

    # --- Research Defaults ---
    default_depth: Literal["fast", "deep"] = "fast"

    # --- Logging ---
    log_level: str = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance. Call once at startup."""
    return Settings()

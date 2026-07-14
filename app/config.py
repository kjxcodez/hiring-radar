"""Application configuration loaded from environment / .env file.

Import the singleton:
    from app.config import settings
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration for hiring-radar.

    Values are read from the environment first, then from a ``.env`` file in
    the working directory.  Sensitive fields (API keys) default to ``None``
    so the tool stays functional for keyless scraping.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- AI / LLM ---
    openrouter_api_key: str | None = None
    openrouter_model: str = "openai/gpt-4o-mini"

    # --- Output ---
    output_dir: Path = Path("output")

    # --- HTTP behaviour ---
    request_delay_seconds: float = Field(default=1.5, ge=0.0)
    user_agent: str = (
        "hiring-radar/0.1 (personal use; github.com/<placeholder>/hiring-radar)"
    )

    # --- Logging ---
    log_level: str = "INFO"


# ---------------------------------------------------------------------------
# Module-level singleton — import this everywhere:
#   from app.config import settings
# ---------------------------------------------------------------------------
settings = Settings()

# Ensure output directories exist as soon as the module is imported.
settings.output_dir.mkdir(parents=True, exist_ok=True)
(settings.output_dir / "logs").mkdir(parents=True, exist_ok=True)

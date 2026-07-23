"""Application configuration loaded from environment / .env file and config.yaml.

Import the singletons:
    from app.config import settings, yaml_config
"""

from pathlib import Path
import yaml
from loguru import logger
from pydantic import BaseModel, Field
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
    openrouter_model: str = "openrouter/free"
    google_api_key: str | None = None
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    groq_api_key: str | None = None
    deepseek_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # --- Output ---
    output_dir: Path = Path("output")

    # --- HTTP behaviour ---
    request_delay_seconds: float = Field(default=1.5, ge=0.0)
    user_agent: str = (
        "hiring-radar/0.1 (personal use; github.com/kjxcodez/hiring-radar)"
    )

    # --- Logging ---
    log_level: str = "INFO"

    # --- SMTP / Outreach ---
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_app_password: str | None = None

    # --- Telegram Notification ---
    telegram_bot_token: str | None = None

    # --- Resume ---
    resume_path: Path | None = None



# ===========================================================================
# Precedence Rule:
# secrets and infra-level values (API keys, paths, log level) stay in `.env`/Settings;
# user preference values (default profile, telegram chat id, email from-name)
# live in config.yaml/YamlConfig. Don't duplicate a field in both places.
# ===========================================================================

class TelegramConfig(BaseModel):
    """Configuration for Telegram notifications."""
    enabled: bool = False
    chat_id: str = ""


class EmailConfig(BaseModel):
    """Configuration for email outreach."""
    from_name: str = "Kapil Kumar Jangid"
    from_address: str = ""


class ExportConfig(BaseModel):
    """Configuration for exports."""
    default_format: str = "csv"


class AgentConfig(BaseModel):
    """Configuration for agent experience and terminal UX."""
    show_progress: bool = True
    show_debug_logs: bool = False
    stream_output: bool = True
    animations: bool = True
    theme: str = "default"
    verbosity: str = "normal"


class UIConfig(BaseModel):
    """Configuration for CLI UI and visual aesthetics."""
    theme: str = "default"
    animations: bool = True
    streaming: bool = True
    markdown: bool = True
    progress: bool = True
    status_updates: bool = True
    show_execution_time: bool = True
    compact_mode: bool = False
    unicode: bool = True
    typing_effect: bool = False


class LLMConfig(BaseModel):
    """Configuration for LLM Orchestration."""
    default_provider: str = "google"
    default_model: str = "gemini-2.5-flash"
    timeout: int = 120
    retries: int = 3
    temperature: float = 0.2
    max_tokens: int = 8000
    stream: bool = True
    fallback_chain: list[str] = ["google", "openrouter", "openai", "anthropic", "groq", "ollama"]


class YamlConfig(BaseModel):
    """User preferences loaded from a non-secret config.yaml file."""
    default_profile: str = "frontend"
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    email: EmailConfig = Field(default_factory=EmailConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    ui: UIConfig = Field(default_factory=UIConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)


def load_yaml_config(path: Path = Path("config.yaml")) -> YamlConfig:
    """Read a YAML file if present, otherwise return YamlConfig with defaults.

    Never crashes on missing config.yaml.
    """
    if not path.exists():
        logger.info(
            "config: '{path}' not found. Using defaults. "
            "You can create one by copying 'config.example.yaml'.",
            path=path
        )
        return YamlConfig()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as exc:
        logger.warning(
            "config: Failed to parse '{path}' ({exc}). Using defaults.",
            path=path,
            exc=exc
        )
        return YamlConfig()

    if not isinstance(data, dict):
        logger.warning(
            "config: Invalid YAML format in '{path}' (expected dictionary). Using defaults.",
            path=path
        )
        return YamlConfig()

    try:
        return YamlConfig.model_validate(data)
    except Exception as exc:
        logger.warning(
            "config: Validation failed for '{path}' ({exc}). Using defaults.",
            path=path,
            exc=exc
        )
        return YamlConfig()


# ---------------------------------------------------------------------------
# Module-level singletons — import these everywhere:
#   from app.config import settings, yaml_config
# ---------------------------------------------------------------------------
settings = Settings()
yaml_config = load_yaml_config()

# Ensure output directories exist as soon as the module is imported.
settings.output_dir.mkdir(parents=True, exist_ok=True)
(settings.output_dir / "logs").mkdir(parents=True, exist_ok=True)


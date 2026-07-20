from __future__ import annotations

from pathlib import Path
from typing import Any
import orjson

from app.repositories import CompanyRepository, ApplicationRepository
from app.notify.telegram import send_telegram_message
from app.config import Settings, YamlConfig

class HealthService:
    def __init__(
        self,
        company_repo: CompanyRepository,
        application_repo: ApplicationRepository,
        settings: Settings,
        yaml_config: YamlConfig,
    ):
        self.company_repo = company_repo
        self.application_repo = application_repo
        self.settings = settings
        self.yaml_config = yaml_config

    def run_checks(self) -> dict[str, Any]:
        """Perform system diagnostics checking files, credentials, and connectivity."""
        checks = {}
        all_ok = True

        # .env
        env_file = Path(".env")
        checks["env_present"] = env_file.exists()

        # config.yaml
        yaml_file = Path("config.yaml")
        checks["config_yaml_present"] = yaml_file.exists()

        # API key
        if self.settings.openrouter_api_key:
            checks["openrouter_api_key_ok"] = True
        else:
            checks["openrouter_api_key_ok"] = False
            all_ok = False

        # Database formats
        db_path = self.settings.output_dir / "companies.json"
        if not db_path.exists():
            checks["companies_db_state"] = "missing"
        else:
            try:
                companies = self.company_repo.load_all()
                checks["companies_db_state"] = f"ok ({len(companies)} companies)"
            except Exception:
                checks["companies_db_state"] = "corrupt"
                all_ok = False

        apps_path = self.settings.output_dir / "applications.json"
        if not apps_path.exists():
            checks["applications_db_state"] = "empty"
        else:
            try:
                apps = self.application_repo.load_all()
                checks["applications_db_state"] = f"ok ({len(apps)} applications)"
            except Exception:
                checks["applications_db_state"] = "corrupt"
                all_ok = False

        # Telegram
        bot_token = self.settings.telegram_bot_token
        chat_id = self.yaml_config.telegram.chat_id
        enabled = self.yaml_config.telegram.enabled

        checks["telegram_configured"] = bool(bot_token and chat_id)
        checks["telegram_enabled"] = enabled

        checks["all_ok"] = all_ok
        return checks

    def test_telegram(self) -> bool:
        """Send test message to Telegram."""
        return send_telegram_message(
            "🔔 *Hiring Radar Test Notification*\n\n"
            "If you see this, your Telegram Bot integration is working correctly! 🎉"
        )

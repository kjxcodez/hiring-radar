#!/usr/bin/env python3
"""Health Check script for Hiring Radar.

Performs diagnostic checks on settings, files, and notification configurations.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path so we can import app modules directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import orjson
from rich.console import Console

# Disable emoji encoding warnings/crashes on Windows by fallback to safe ASCII
console = Console(legacy_windows=True) if sys.platform == "win32" else Console()


def run_checks() -> bool:
    all_ok = True

    console.print("\n[bold purple]=== Hiring Radar System Diagnostics ===[/bold purple]\n")

    # 1. Check Configuration & Environment
    console.print("[bold]1. Configuration & Settings:[/bold]")
    try:
        from app.config import settings, yaml_config

        # Check .env presence
        env_file = Path(".env")
        if env_file.exists():
            console.print("  [green][OK][/green] .env file is present.")
        else:
            console.print("  [yellow][WARN][/yellow] .env file is missing (using system env variables).")

        # Check config.yaml presence
        yaml_file = Path("config.yaml")
        if yaml_file.exists():
            console.print("  [green][OK][/green] config.yaml file is present.")
        else:
            console.print("  [yellow][WARN][/yellow] config.yaml file is missing (using default preferences).")

        # Validate OpenRouter settings
        if settings.openrouter_api_key:
            console.print("  [green][OK][/green] OPENROUTER_API_KEY is configured.")
        else:
            console.print("  [red][FAIL][/red] OPENROUTER_API_KEY is missing.")
            all_ok = False

        console.print("  [green][OK][/green] settings and user config loaded successfully.")

    except Exception as exc:  # noqa: BLE001
        console.print(f"  [red][FAIL][/red] Failed to load configuration: {exc}")
        all_ok = False

    console.print()

    # 2. Check Database Files
    console.print("[bold]2. Database Integrity:[/bold]")
    try:
        from app.config import settings

        db_path = settings.output_dir / "companies.json"
        if not db_path.exists():
            console.print(f"  [yellow][WARN][/yellow] database '{db_path}' does not exist yet (run discover first).")
        else:
            data = db_path.read_bytes()
            companies = orjson.loads(data)
            if isinstance(companies, list):
                console.print(f"  [green][OK][/green] '{db_path}' is readable and valid JSON ({len(companies)} companies).")
            else:
                console.print(f"  [red][FAIL][/red] '{db_path}' format is invalid (expected JSON array).")
                all_ok = False

        apps_path = settings.output_dir / "applications.json"
        if not apps_path.exists():
            console.print(f"  [green][OK][/green] Applications db '{apps_path}' is empty/not started.")
        else:
            apps_data = apps_path.read_bytes()
            apps = orjson.loads(apps_data)
            if isinstance(apps, dict):
                console.print(f"  [green][OK][/green] '{apps_path}' is readable and valid JSON ({len(apps)} applications).")
            else:
                console.print(f"  [red][FAIL][/red] '{apps_path}' format is invalid (expected JSON object).")
                all_ok = False

    except Exception as exc:  # noqa: BLE001
        console.print(f"  [red][FAIL][/red] Failed to verify database: {exc}")
        all_ok = False

    console.print()

    # 3. Check Telegram Notification Configuration
    console.print("[bold]3. Telegram Notifications:[/bold]")
    try:
        from app.notify.telegram import send_telegram_message
        from app.config import settings, yaml_config

        bot_token = settings.telegram_bot_token
        chat_id = yaml_config.telegram.chat_id
        enabled = yaml_config.telegram.enabled

        if bot_token and chat_id:
            console.print(f"  - Bot Token: [green]configured[/green] (starts with: '{bot_token[:8]}...')")
            console.print(f"  - Chat ID:   [green]configured[/green] ('{chat_id}')")
            console.print(f"  - Enabled:   {enabled}")

            if not enabled:
                console.print("  [yellow][WARN][/yellow] Telegram is configured but disabled in config.yaml.")
            else:
                console.print("  [cyan][INFO][/cyan] Attempting to send a diagnostics test message...")
                success = send_telegram_message("Health Check: Diagnostics test message delivered successfully!")
                if success:
                    console.print("  [green][OK][/green] Telegram diagnostics test message sent successfully.")
                else:
                    console.print("  [red][FAIL][/red] Telegram sendMessage request failed. Check bot privileges.")
                    all_ok = False
        else:
            console.print("  [yellow][WARN][/yellow] Telegram notifications not configured (bot token or chat id is missing).")

    except Exception as exc:  # noqa: BLE001
        console.print(f"  [red][FAIL][/red] Failed to test Telegram notifications: {exc}")
        all_ok = False

    console.print()

    # Final synthesized report
    if all_ok:
        console.print("[bold green]System Health Check: ALL CHECKS PASSED SUCCESSFULLY![/bold green]\n")
    else:
        console.print("[bold red]System Health Check: SOME CHECKS FAILED! Check error diagnostics above.[/bold red]\n")

    return all_ok


if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 1)

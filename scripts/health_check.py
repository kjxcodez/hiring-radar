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
    from app.services.config import ServiceContainer
    container = ServiceContainer()
    health_service = container.health_service

    console.print("\n[bold purple]=== Hiring Radar System Diagnostics ===[/bold purple]\n")

    # Call service
    res = health_service.run_checks()

    # 1. Check Configuration & Environment
    console.print("[bold]1. Configuration & Settings:[/bold]")
    if res["env_present"]:
        console.print("  [green][OK][/green] .env file is present.")
    else:
        console.print("  [yellow][WARN][/yellow] .env file is missing (using system env variables).")

    if res["config_yaml_present"]:
        console.print("  [green][OK][/green] config.yaml file is present.")
    else:
        console.print("  [yellow][WARN][/yellow] config.yaml file is missing (using default preferences).")

    if res["openrouter_api_key_ok"]:
        console.print("  [green][OK][/green] OPENROUTER_API_KEY is configured.")
    else:
        console.print("  [red][FAIL][/red] OPENROUTER_API_KEY is missing.")

    if res["openrouter_api_key_ok"]:
        console.print("  [green][OK][/green] settings and user config loaded successfully.")

    console.print()

    # 2. Check Database Files
    console.print("[bold]2. Database Integrity:[/bold]")
    co_state = res["companies_db_state"]
    if co_state == "missing":
        db_path = container.settings.output_dir / "companies.json"
        console.print(f"  [yellow][WARN][/yellow] database '{db_path}' does not exist yet (run discover first).")
    elif co_state == "corrupt":
        db_path = container.settings.output_dir / "companies.json"
        console.print(f"  [red][FAIL][/red] '{db_path}' format is invalid (expected JSON array).")
    else:
        db_path = container.settings.output_dir / "companies.json"
        num_cos = co_state.split("(")[1].split()[0]
        console.print(f"  [green][OK][/green] '{db_path}' is readable and valid JSON ({num_cos} companies).")

    app_state = res["applications_db_state"]
    apps_path = container.settings.output_dir / "applications.json"
    if app_state == "empty":
        console.print(f"  [green][OK][/green] Applications db '{apps_path}' is empty/not started.")
    elif app_state == "corrupt":
        console.print(f"  [red][FAIL][/red] '{apps_path}' format is invalid (expected JSON object).")
    else:
        num_apps = app_state.split("(")[1].split()[0]
        console.print(f"  [green][OK][/green] '{apps_path}' is readable and valid JSON ({num_apps} applications).")

    console.print()

    # 3. Check Telegram Notification Configuration
    console.print("[bold]3. Telegram Notifications:[/bold]")
    bot_token = container.settings.telegram_bot_token
    chat_id = container.yaml_config.telegram.chat_id
    enabled = container.yaml_config.telegram.enabled

    if bot_token and chat_id:
        console.print(f"  - Bot Token: [green]configured[/green] (starts with: '{bot_token[:8]}...')")
        console.print(f"  - Chat ID:   [green]configured[/green] ('{chat_id}')")
        console.print(f"  - Enabled:   {enabled}")

        if not enabled:
            console.print("  [yellow][WARN][/yellow] Telegram is configured but disabled in config.yaml.")
        else:
            console.print("  [cyan][INFO][/cyan] Attempting to send a diagnostics test message...")
            success = health_service.test_telegram()
            if success:
                console.print("  [green][OK][/green] Telegram diagnostics test message sent successfully.")
            else:
                console.print("  [red][FAIL][/red] Telegram sendMessage request failed. Check bot privileges.")
    else:
        console.print("  [yellow][WARN][/yellow] Telegram notifications not configured (bot token or chat id is missing).")

    console.print()

    all_ok = res["all_ok"]
    if all_ok:
        console.print("[bold green]System Health Check: ALL CHECKS PASSED SUCCESSFULLY![/bold green]\n")
    else:
        console.print("[bold red]System Health Check: SOME CHECKS FAILED! Check error diagnostics above.[/bold red]\n")

    return all_ok


if __name__ == "__main__":
    success = run_checks()
    sys.exit(0 if success else 1)

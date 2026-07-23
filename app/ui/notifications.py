"""Notification display panels styled using Rich."""

from __future__ import annotations

from rich.panel import Panel
from app.cli.common import console


def show_success(message: str) -> None:
    """Print success notification card."""
    console.print(Panel(message, title="✅ Success", border_style="green"))


def show_warning(message: str) -> None:
    """Print warning notification card."""
    console.print(Panel(message, title="⚠️ Warning", border_style="yellow"))


def show_error(message: str) -> None:
    """Print error notification card."""
    console.print(Panel(message, title="❌ Error", border_style="red"))


def show_info(message: str) -> None:
    """Print informational notification card."""
    console.print(Panel(message, title="ℹ️ Info", border_style="cyan"))

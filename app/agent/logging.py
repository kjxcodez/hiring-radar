"""Logging isolation for the Hiring Radar conversational agent."""

from __future__ import annotations

import sys
from pathlib import Path
from loguru import logger


def setup_agent_logging(show_debug_logs: bool = False) -> None:
    """Redirect all developer logs to hiring-radar.log and configure terminal isolation."""
    # 1. Drop existing sinks (console, files, etc.)
    logger.remove()

    # 2. Add File Sink for ALL debug logs
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "hiring-radar.log"
    
    logger.add(
        sink=str(log_file),
        level="DEBUG",
        colorize=False,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        ),
        encoding="utf-8",
    )

    # 3. Add Console/Terminal Sink ONLY if debug logs are requested
    if show_debug_logs:
        logger.add(
            sink=sys.stderr,
            level="DEBUG",
            colorize=True,
            format=(
                "<green>{time:HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<level>{message}</level>"
            ),
        )

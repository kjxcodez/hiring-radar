"""Logging isolation for the Hiring Radar conversational agent."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from loguru import logger


def setup_agent_logging(show_debug_logs: bool = False) -> None:
    """Redirect all developer logs (loguru and standard logging) to hiring-radar.log and isolate console."""
    # 1. Isolate Loguru
    logger.remove()
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

    # 2. Isolate standard Python logging
    root_logger = logging.getLogger()
    # Remove existing handlers (like RichHandler added by FastMCP)
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    # Direct all standard logging to the log file
    file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    root_logger.setLevel(logging.DEBUG)

    # Set library-specific logger levels
    if not show_debug_logs:
        # Prevent console output from propagating
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("mcp").setLevel(logging.WARNING)
    else:
        # Direct standard logging to stderr as well if debug logs are enabled
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(logging.DEBUG)
        console_formatter = logging.Formatter(
            "\033[32m%(asctime)s\033[0m | \033[1;35m%(levelname)-8s\033[0m | %(name)s | %(message)s",
            datefmt="%H:%M:%S"
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
        
        logging.getLogger("httpx").setLevel(logging.DEBUG)
        logging.getLogger("httpcore").setLevel(logging.DEBUG)
        logging.getLogger("mcp").setLevel(logging.DEBUG)

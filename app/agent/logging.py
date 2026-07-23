"""Logging isolation for the Hiring Radar conversational agent."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from loguru import logger


def setup_agent_logging(show_debug_logs: bool = False) -> None:
    """Legacy entry point, delegates to a default session-wide isolation context."""
    context = AgentLoggingContext(show_debug_logs=show_debug_logs)
    context.__enter__()


class AgentLoggingContext:
    """Context manager to isolate developer logs and ensure a silent console output.

    It captures pre-existing logging state, clears console log handlers (such as
    RichHandler or StreamHandler), redirects standard library loggers and Loguru
    to file outputs, and restores the original configuration upon exit.
    """

    def __init__(self, show_debug_logs: bool = False, log_file: Path | str | None = None) -> None:
        self.show_debug_logs = show_debug_logs
        if log_file:
            self.log_file = Path(log_file)
        else:
            self.log_file = Path("logs/hiring-radar.log")
            
        self._old_handlers = []
        self._old_root_level = None
        self._old_propagate_settings = {}
        self._old_loguru_handlers = []

    def __enter__(self) -> AgentLoggingContext:
        # 1. Capture Loguru handlers and clear sinks
        self._old_loguru_handlers = list(logger._core.handlers.values())
        logger.remove()

        # 2. Capture root logger state
        root_logger = logging.getLogger()
        self._old_root_level = root_logger.level
        self._old_handlers = list(root_logger.handlers)

        # Clear root logger handlers to decouple console handlers
        for h in self._old_handlers:
            root_logger.removeHandler(h)

        # 3. Ensure log destination directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # 4. Configure Loguru file sink (always DEBUG)
        logger.add(
            sink=str(self.log_file),
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

        if self.show_debug_logs:
            # Re-enable console output under debug logs setting
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

        # 5. Configure standard root logger file handler (always DEBUG)
        file_handler = logging.FileHandler(str(self.log_file), encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
        root_logger.setLevel(logging.DEBUG)

        if self.show_debug_logs:
            # Enable standard logs to console under debug mode
            console_handler = logging.StreamHandler(sys.stderr)
            console_handler.setLevel(logging.DEBUG)
            console_formatter = logging.Formatter(
                "\033[32m%(asctime)s\033[0m | \033[1;35m%(levelname)-8s\033[0m | %(name)s | %(message)s",
                datefmt="%H:%M:%S"
            )
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)

        # 6. Isolate library-specific loggers
        # Ensure library loggers are set to DEBUG/emit level so they write to file via propagation,
        # but remain silent on the console when show_debug_logs is False.
        loggers_to_isolate = ["httpx", "httpcore", "openai", "mcp", "FastMCP", "urllib3", "asyncio"]
        for name in loggers_to_isolate:
            lib_logger = logging.getLogger(name)
            self._old_propagate_settings[name] = (lib_logger.level, lib_logger.propagate)
            
            lib_logger.setLevel(logging.DEBUG)
            lib_logger.propagate = True

        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # 1. Restore standard root logger state
        root_logger = logging.getLogger()
        for h in list(root_logger.handlers):
            root_logger.removeHandler(h)
        for h in self._old_handlers:
            root_logger.addHandler(h)
        if self._old_root_level is not None:
            root_logger.setLevel(self._old_root_level)

        # 2. Restore library propagate settings
        for name, (level, propagate) in self._old_propagate_settings.items():
            lib_logger = logging.getLogger(name)
            lib_logger.setLevel(level)
            lib_logger.propagate = propagate

        # 3. Restore Loguru state (re-runs global CLI logging initialization)
        logger.remove()
        try:
            from app.utils import setup_logging
            setup_logging()
        except Exception:
            pass

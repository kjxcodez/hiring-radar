"""Logging configuration inspector and diagnostics utility."""

from __future__ import annotations

import logging
from typing import Any


def inspect_logging_infrastructure() -> str:
    """Scan all active Python loggers, handlers, and formats, and return a report string."""
    report = []
    report.append("======================================================================")
    report.append("                      LOGGING INFRASTRUCTURE REPORT                   ")
    report.append("======================================================================")

    # 1. Root Logger
    root = logging.getLogger()
    report.append("\nRoot Logger:")
    report.append(f"  Level: {root.level} ({logging.getLevelName(root.level)})")
    report.append(f"  Propagate: {root.propagate}")
    report.append("  Handlers:")
    if not root.handlers:
        report.append("    None")
    for idx, h in enumerate(root.handlers, 1):
        report.append(f"    {idx}. {h.__class__.__name__}")
        report.append(f"       Level: {h.level} ({logging.getLevelName(h.level)})")
        report.append(f"       Stream/Destination: {getattr(h, 'stream', getattr(h, 'baseFilename', 'Unknown'))}")
        if h.formatter:
            report.append(f"       Formatter: {h.formatter.__class__.__name__} (Format: {getattr(h.formatter, '_fmt', 'Unknown')})")

    # 2. Known Active Loggers
    report.append("\nActive Loggers Registry:")
    logger_manager = logging.root.manager
    loggers = [logging.getLogger(name) for name in logger_manager.loggerDict]
    
    # Add root and common libraries
    common_names = ["httpx", "httpcore", "urllib3", "requests", "openai", "openrouter", "rich", "typer"]
    for name in common_names:
        if name not in logger_manager.loggerDict:
            loggers.append(logging.getLogger(name))

    for logger in sorted(loggers, key=lambda l: l.name):
        # Only show loggers that have non-default level, custom handlers, or propagate set to False
        if logger.handlers or logger.level != logging.NOTSET or logger.propagate is False:
            report.append(f"\n  Logger: {logger.name}")
            report.append(f"    Level: {logger.level} ({logging.getLevelName(logger.level)})")
            report.append(f"    Propagate: {logger.propagate}")
            report.append("    Handlers:")
            if not logger.handlers:
                report.append("      None")
            for idx, h in enumerate(logger.handlers, 1):
                report.append(f"      {idx}. {h.__class__.__name__}")
                report.append(f"         Level: {h.level} ({logging.getLevelName(h.level)})")
                report.append(f"         Stream/Destination: {getattr(h, 'stream', getattr(h, 'baseFilename', 'Unknown'))}")
                if h.formatter:
                    report.append(f"         Formatter: {h.formatter.__class__.__name__}")

    # 3. Loguru Sinks
    report.append("\nLoguru Sinks:")
    try:
        from loguru import logger as loguru_logger
        core = getattr(loguru_logger, "_core", None)
        if core:
            # Retrieve private handlers registry safely
            handlers = getattr(core, "handlers", {})
            if not handlers:
                report.append("  None")
            for h_id, h_entry in handlers.items():
                sink = getattr(h_entry, "_sink", None)
                level = getattr(h_entry, "_levelno", 0)
                level_name = logging.getLevelName(level) if hasattr(logging, "getLevelName") else str(level)
                report.append(f"  Sink ID {h_id}:")
                report.append(f"    Type: {sink.__class__.__name__ if sink else 'Unknown'}")
                report.append(f"    Level: {level} ({level_name})")
                
                # Extract destination details safely
                dest = "Unknown"
                if sink:
                    dest = getattr(sink, "_file", getattr(sink, "_stream", "Unknown"))
                report.append(f"    Destination: {dest}")
        else:
            report.append("  Loguru core not accessible.")
    except Exception as exc:
        report.append(f"  Error loading loguru sinks: {exc}")

    report.append("\n======================================================================")
    return "\n".join(report)


if __name__ == "__main__":
    print(inspect_logging_infrastructure())

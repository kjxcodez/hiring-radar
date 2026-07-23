"""Tests for Phase 3.1.1 Logging Isolation & Silent REPL."""

from __future__ import annotations

import logging
from pathlib import Path

from app.agent.logging import AgentLoggingContext
from app.debug.logging_inspector import inspect_logging_infrastructure


def test_agent_logging_context_silence_and_redirection(tmp_path: Path) -> None:
    """Verify that AgentLoggingContext silences console and redirects logs to file."""
    log_file = tmp_path / "test-hiring-radar.log"
    
    # Pre-existing state
    root = logging.getLogger()
    pre_handlers = list(root.handlers)
    pre_level = root.level
    
    # 1. Enter context
    with AgentLoggingContext(show_debug_logs=False, log_file=log_file):
        # Verify root logger level is DEBUG
        assert root.level == logging.DEBUG
        
        # Verify root logger has ONLY FileHandler and NO other handlers
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], logging.FileHandler)
        assert root.handlers[0].baseFilename == str(log_file.resolve())
        
        # Verify library loggers have propagation enabled and level DEBUG
        httpx_logger = logging.getLogger("httpx")
        assert httpx_logger.level == logging.DEBUG
        assert httpx_logger.propagate is True
        
        # Write log messages
        logging.getLogger("httpx").info("HTTP Request: POST /chat")
        logging.getLogger("app.workflows").warning("executing step 1")
        
    # 2. Exit context (Verify restoration of previous configuration)
    assert root.level == pre_level
    assert list(root.handlers) == pre_handlers
    
    # Verify file content
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "HTTP Request: POST /chat" in content
    assert "executing step 1" in content


def test_agent_logging_context_debug_mode(tmp_path: Path) -> None:
    """Verify that AgentLoggingContext allows console outputs when show_debug_logs is True."""
    log_file = tmp_path / "test-hiring-radar-debug.log"
    
    root = logging.getLogger()
    
    with AgentLoggingContext(show_debug_logs=True, log_file=log_file):
        # Under debug mode, there should be both FileHandler and StreamHandler (console)
        assert len(root.handlers) >= 2
        assert any(isinstance(h, logging.FileHandler) for h in root.handlers)
        assert any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root.handlers)


def test_logging_inspector_diagnostics() -> None:
    """Verify that logging inspector diagnostics report contains PASS/FAILED."""
    report = inspect_logging_infrastructure()
    assert "LOGGING INFRASTRUCTURE REPORT" in report
    assert "Logging isolation:" in report
    assert "PASS" in report or "FAILED" in report

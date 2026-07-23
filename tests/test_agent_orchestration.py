"""Unit tests for Phase 3.1 Logging Isolation, Agent State Synchronization & Orchestration Reliability."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from app.agent.planner import run_agent_turn, build_agent_system_prompt
from app.agent.state_validator import validate_system_state
from app.agent.tools import TOOL_REGISTRY
from app.agent.session import AgentSession
from app.agent.logging import setup_agent_logging
from app.debug.logging_inspector import inspect_logging_infrastructure
from app.debug.diagnostics import run_doctor, inspect_repositories, inspect_memory_state


def test_state_validator_warnings() -> None:
    """Verify that validate_system_state catches inconsistencies across repositories."""
    container_mock = MagicMock()
    settings_mock = MagicMock()
    
    # Mock settings.resume_path to be missing
    settings_mock.resume_path = Path("resumes/non_existent.pdf")
    
    # Mock recommendation repo returning recommendations (which triggers warning since resume is missing)
    container_mock.recommendation_repo.load_recommendations.return_value = [
        {"company_name": "Stripe", "job_title": "Backend Engineer", "score": 0.8}
    ]
    
    # Mock companies repository (with Stripe to avoid empty companies warnings but trigger mismatches)
    co_mock = MagicMock()
    co_mock.dedupe_key.return_value = "stripe_key"
    co_mock.name = "Stripe"
    co_mock.jobs = []
    container_mock.company_repo.load_all.return_value = [co_mock]
    
    # Mock apps referencing non-existent company dedupe key
    app_mock = MagicMock()
    app_mock.company_key = "non_existent_co"
    app_mock.company = None
    app_mock.job = None
    app_mock.status = "applied"
    container_mock.application_repo.load_all.return_value = [app_mock]
    
    # Mock monitoring alert referencing missing company name
    alert_mock = {"company_name": "NonExistentCompany", "event_type": "new_job"}
    container_mock.monitoring_repo.load_alerts.return_value = [alert_mock]

    with patch("app.agent.state_validator.get_container", return_value=container_mock), \
         patch("app.agent.state_validator.settings", settings_mock):
        warnings = validate_system_state()
        
        # Verify warnings are triggered
        assert len(warnings) > 0
        assert any("resume is currently loaded" in w for w in warnings)
        assert any("non_existent_co" in w for w in warnings)
        assert any("NonExistentCompany" in w for w in warnings)


def test_read_only_tools_registered() -> None:
    """Verify that read-only query tools are registered and return structured repository records."""
    assert "list_applications" in TOOL_REGISTRY
    assert "list_alerts" in TOOL_REGISTRY
    assert "list_companies" in TOOL_REGISTRY

    container_mock = MagicMock()
    
    # 1. list_applications test
    app_mock = {
        "company": {"name": "Wealthfront"},
        "job": {"job_title": "Backend"},
        "status": "applied",
        "next_followup": "2026-08-01"
    }
    container_mock.application_repo.load_all.return_value = [app_mock]
    
    # 2. list_alerts test
    alert_mock = {"company_name": "Vercel", "event_type": "new_job"}
    container_mock.monitoring_repo.load_alerts.return_value = [alert_mock]
    
    # 3. list_companies test
    company_mock = MagicMock()
    company_mock.model_dump.return_value = {"name": "Stripe", "domain": "stripe.com"}
    container_mock.company_repo.load_all.return_value = [company_mock]

    with patch("app.agent.tools.get_container", return_value=container_mock):
        # Retrieve implementations
        list_apps_fn = TOOL_REGISTRY["list_applications"].fn
        list_alerts_fn = TOOL_REGISTRY["list_alerts"].fn
        list_companies_fn = TOOL_REGISTRY["list_companies"].fn
        
        apps_res = list_apps_fn()
        assert len(apps_res) == 1
        assert apps_res[0]["company_name"] == "Wealthfront"
        assert apps_res[0]["status"] == "applied"
        
        alerts_res = list_alerts_fn(limit=5)
        assert len(alerts_res) == 1
        assert alerts_res[0]["company_name"] == "Vercel"
        
        cos_res = list_companies_fn(limit=5)
        assert len(cos_res) == 1
        assert cos_res[0]["name"] == "Stripe"


def test_planner_pre_routing() -> None:
    """Verify run_agent_turn pre-routes database lookup queries to tools, avoiding LLM calls."""
    session = AgentSession()
    history = []
    
    # Target queries triggers pre-routing
    queries = [
        "Show my applications",
        "What applications are pending?",
        "Show alerts please",
        "Recommend jobs for me"
    ]
    
    container_mock = MagicMock()
    container_mock.application_repo.load_all.return_value = []
    container_mock.monitoring_repo.load_alerts.return_value = []
    container_mock.recommendation_repo.load_recommendations.return_value = []
    
    # Mock settings OpenRouter key
    with patch("app.agent.planner.settings") as mock_settings, \
         patch("app.cli.common.get_container", return_value=container_mock), \
         patch("app.agent.tools.get_container", return_value=container_mock), \
         patch("app.agent.planner._post_with_retry") as mock_post:
        
        mock_settings.openrouter_api_key = "test_key"
        mock_settings.openrouter_model = "test_model"
        
        # Setup mock completion response
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"choices": [{"message": {"content": "Here are details."}}]}
        mock_post.return_value = mock_resp
        
        for q in queries:
            hist = []
            res = run_agent_turn(q, hist, session=session)
            
            # Verify the tools were executed and recorded in the history
            assert len(hist) >= 3  # User message, Mock Assistant tool-call, Tool Result
            assert hist[1]["role"] == "assistant"
            assert "tool_calls" in hist[1]
            assert hist[2]["role"] == "tool"


def test_logging_isolation_cleanup() -> None:
    """Verify setup_agent_logging clears old handlers and isolates propagation."""
    root = logging.getLogger()
    # Add a mock handler to simulate FastMCP registration
    mock_h = logging.StreamHandler(sys.stderr)
    root.addHandler(mock_h)
    assert mock_h in root.handlers
    
    # Run setup
    setup_agent_logging(show_debug_logs=False)
    
    # Verify mock handler is cleaned up and only FileHandler is present
    assert mock_h not in root.handlers
    assert any(isinstance(h, logging.FileHandler) for h in root.handlers)
    assert not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler) for h in root.handlers)


def test_diagnostics_smoke() -> None:
    """Run diagnostics functions to ensure no crashes occur."""
    container_mock = MagicMock()
    container_mock.company_repo.filepath = "companies.json"
    container_mock.company_repo.load_all.return_value = []
    container_mock.application_repo.filepath = "applications.json"
    container_mock.application_repo.load_all.return_value = []
    container_mock.memory_repo.filepath = "agent_memory.json"
    container_mock.memory_repo.load.return_value = {"preferences": {}, "rejected_companies": [], "past_decisions": []}
    container_mock.saved_search_repo.filepath = "saved_searches.json"
    container_mock.saved_search_repo.load_all.return_value = []
    container_mock.monitoring_repo.events_path = "events.json"
    container_mock.monitoring_repo.load_events.return_value = []
    container_mock.monitoring_repo.load_alerts.return_value = []

    with patch("app.debug.diagnostics.get_container", return_value=container_mock), \
         patch("app.debug.diagnostics.console.print") as mock_print, \
         patch("app.agent.state_validator.get_container", return_value=container_mock):
        
        run_doctor()
        assert mock_print.called
        
        mock_print.reset_mock()
        inspect_repositories()
        assert mock_print.called
        
        mock_print.reset_mock()
        inspect_memory_state()
        assert mock_print.called

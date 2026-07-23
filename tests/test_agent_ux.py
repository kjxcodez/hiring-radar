"""Unit tests for Phase 3.0 Agent Experience, Terminal UX, and Session variables."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from loguru import logger
from rich.panel import Panel

from app.agent.events import ThinkingEvent, SearchingEvent, ProgressEvent
from app.agent.translator import translate_event
from app.agent.progress import AgentProgressRenderer
from app.agent.session import AgentSession
from app.agent.cards import (
    render_company_card,
    render_recommendation_card,
    render_application_card,
    render_monitoring_card,
    print_tool_result_card,
)
from app.agent.logging import setup_agent_logging
from app.agent.planner import build_agent_system_prompt
from app.cli.commands.system import show_repl_help, show_agent_dashboard
from app.workflows.events import WorkflowStarted, StepStarted, StepFinished, WorkflowCompleted


def test_agent_events() -> None:
    """Verify agent events instantiate correctly with default values."""
    think = ThinkingEvent()
    assert think.message == "Thinking..."
    
    search = SearchingEvent()
    assert search.message == "Searching opportunities..."
    
    prog = ProgressEvent(task_name="indexing", status="running", message="Almost done")
    assert prog.task_name == "indexing"
    assert prog.status == "running"
    assert prog.message == "Almost done"


def test_event_translator() -> None:
    """Verify workflow steps and lifecycle events translate to friendly terms."""
    ev1 = WorkflowStarted(workflow_name="intelligence", execution_id="123")
    assert translate_event(ev1) == "Researching company intelligence..."
    
    ev2 = StepStarted(workflow_name="discover", execution_id="123", step_name="GreenhouseDiscover")
    assert translate_event(ev2) == "Fetching Greenhouse listings..."
    
    ev3 = StepFinished(workflow_name="discover", execution_id="123", step_name="GreenhouseDiscover")
    assert translate_event(ev3) is None  # Finished step doesn't show transition line


def test_progress_renderer() -> None:
    """Verify progress renderer handles events and structures Rich display correctly."""
    renderer = AgentProgressRenderer(show_progress=True, animations=False)
    
    # Simulate workflow start
    ev_start = WorkflowStarted(workflow_name="intelligence", execution_id="123")
    renderer.handle_event(ev_start)
    assert renderer.active_wf == "Researching company intelligence"
    
    # Simulate step start
    ev_step = StepStarted(workflow_name="intelligence", execution_id="123", step_name="EnrichIntelligence")
    renderer.handle_event(ev_step)
    assert len(renderer.steps) == 1
    assert renderer.steps[0]["name"] == "Analyzing firmographics and signals"
    assert renderer.steps[0]["status"] == "running"
    
    # Simulate step complete
    ev_step_finish = StepFinished(workflow_name="intelligence", execution_id="123", step_name="EnrichIntelligence")
    renderer.handle_event(ev_step_finish)
    assert renderer.steps[0]["status"] == "success"
    
    # Check render structure
    group = renderer.render()
    assert len(group.renderables) == 2  # header + 1 step


def test_agent_session() -> None:
    """Verify AgentSession tracks tool calls, workflow completions, and memories."""
    session = AgentSession()
    assert session.jobs_searched == 0
    assert session.loaded_resume is None
    
    # Record search jobs
    session.record_tool_call("search_jobs", {"sources": ["greenhouse"]})
    assert session.jobs_searched == 1
    
    # Record view company
    session.record_tool_call("get_company", {"name": "Wealthfront"})
    assert "Wealthfront" in session.companies_viewed
    assert "Wealthfront" in session.discussed_companies
    
    # Workflow tracking
    session.record_workflow_execution("discover")
    assert "discover" in session.workflows_executed
    
    # Clear session
    session.clear()
    assert len(session.companies_viewed) == 0
    assert session.jobs_searched == 0


def test_cards_rendering() -> None:
    """Verify rich cards generate without crashing."""
    # 1. Recommendation card
    rec_data = {
        "job_title": "Staff Engineer",
        "company_name": "Wealthfront",
        "score": 0.9,
        "job_url": "https://wealthfront.com/jobs/1",
        "strengths": ["Python", "System Design"],
        "weaknesses": ["Go"],
        "explanation": {"summary": "Strong fit."},
    }
    rec_panel = render_recommendation_card(rec_data)
    assert isinstance(rec_panel, Panel)
    assert "Staff Engineer" in str(rec_panel.title)
    
    # 2. Company card
    co_data = {
        "name": "Vercel",
        "domain": "vercel.com",
        "company_size": "500-1000",
        "intelligence": {
            "business": {"industry": "Cloud Infrastructure", "headquarters": "San Francisco"},
            "engineering": {"languages": ["TypeScript", "Rust"]},
        }
    }
    co_panel = render_company_card(co_data)
    assert isinstance(co_panel, Panel)
    assert "Vercel" in str(co_panel.title)
    
    # 3. Application card
    app_data = {
        "company": {"name": "Vercel"},
        "job": {"job_title": "Frontend Engineer"},
        "status": "applied",
        "next_followup": "2026-08-01",
        "cover_letter_version": "Dear Hiring Manager, I am excited...",
    }
    app_panel = render_application_card(app_data)
    assert isinstance(app_panel, Panel)
    assert "Vercel" in str(app_panel.title)
    
    # 4. Monitoring card
    alerts = [
        {"event_type": "new_job", "company_name": "Stripe", "metadata": {"title": "Staff Frontend"}},
        {"event_type": "status_change", "company_name": "Vercel", "metadata": {"status": "interviewing"}},
    ]
    alerts_panel = render_monitoring_card(alerts)
    assert isinstance(alerts_panel, Panel)
    
    # 5. Print tool result card smoke check
    with patch("app.cli.common.console.print") as mock_print:
        print_tool_result_card("get_company", co_data)
        assert mock_print.called


def test_agent_logging_setup(tmp_path: Path) -> None:
    """Verify setup_agent_logging isolates logging without throwing errors."""
    with patch("loguru.logger.add") as mock_add, patch("loguru.logger.remove") as mock_remove:
        setup_agent_logging(show_debug_logs=True)
        assert mock_remove.called
        assert mock_add.call_count == 2  # file sink + console sink


def test_planner_prompt_injection() -> None:
    """Verify build_agent_system_prompt injects session state variables."""
    session = AgentSession()
    session.loaded_resume = Path("path/to/resume.pdf")
    session.discussed_companies = ["Wealthfront", "Vercel"]
    
    with patch("app.agent.memory.load_memory") as mock_load, patch("app.ai.prompts.get_prompt") as mock_prompt:
        mock_load.return_value = {"preferences": {}, "rejected_companies": []}
        mock_tpl = MagicMock()
        mock_tpl.system_prompt_template.format.return_value = "Base Prompt"
        mock_prompt.return_value = mock_tpl
        
        full_prompt = build_agent_system_prompt(session)
        assert "Base Prompt" in full_prompt
        assert "resume.pdf" in full_prompt
        assert "Wealthfront, Vercel" in full_prompt


def test_repl_help_and_dashboard() -> None:
    """Smoke check displaying help and dashboard functions."""
    session = AgentSession()
    with patch("app.cli.common.console.print") as mock_print:
        show_repl_help()
        assert mock_print.called
        
    with patch("app.cli.common.console.print") as mock_print:
        show_agent_dashboard(session)
        assert mock_print.called

"""Tests for integrated Reasoning Agent Planner."""

from __future__ import annotations

from unittest.mock import patch, MagicMock
from app.agent.session import AgentSession
from app.agent.planner import run_agent_turn


def test_planner_early_exit() -> None:
    """Verify that direct repository commands bypass LLM completions entirely."""
    session = AgentSession()
    history = []
    
    mock_apps = [
        {"company_name": "Stripe", "job_title": "Backend engineer", "status": "Applied", "next_followup": "2026-08-01"}
    ]
    
    with patch("app.agent.planner.TOOL_REGISTRY") as mock_registry:
        mock_tool = MagicMock()
        mock_tool.fn.return_value = mock_apps
        mock_registry.get.return_value = mock_tool
        mock_registry.__contains__.return_value = True
        
        res = run_agent_turn(
            user_message="Show my applications",
            conversation_history=history,
            session=session
        )
        
        assert "Stripe" in res["reply"]
        assert "Backend engineer" in res["reply"]
        assert session.planning_metrics["unnecessary_llm_calls_avoided"] == 1
        assert session.planning_metrics["successful_plans"] == 1
        assert "list_applications" in res["tool_calls_made"]

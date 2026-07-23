"""Tests for Response Strategy Layer."""

from __future__ import annotations

from app.agent.response_strategy import get_response_strategy_prompt


def test_response_strategy_prompts() -> None:
    """Verify specific styling prompts return for mapped intents."""
    p_rec = get_response_strategy_prompt("recommend_jobs")
    assert "ranked list" in p_rec

    p_co = get_response_strategy_prompt("company_research")
    assert "corporate research report" in p_co

    p_apps = get_response_strategy_prompt("application_status")
    assert "CRM applications" in p_apps

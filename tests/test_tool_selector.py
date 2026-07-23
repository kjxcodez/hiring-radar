"""Tests for Context-Aware Tool Selector."""

from __future__ import annotations

from app.agent.intent import IntentClassification
from app.agent.query_analysis import QueryAnalysis
from app.agent.tool_selector import score_and_select_tools


def test_tool_selector_scoring() -> None:
    """Verify tool scoring weights map correctly based on intent inputs."""
    intent_info = IntentClassification(intent="recommend_jobs", confidence=1.0)
    query_info = QueryAnalysis()
    
    selected = score_and_select_tools(intent_info, query_info)
    assert len(selected) > 0
    assert selected[0][0] == "recommend"
    assert selected[0][1] == 1.0

    intent_info_co = IntentClassification(intent="company_research", confidence=1.0)
    query_info_co = QueryAnalysis(company_names=["Stripe"])
    selected_co = score_and_select_tools(intent_info_co, query_info_co)
    assert len(selected_co) > 0
    assert selected_co[0][0] == "research_company"

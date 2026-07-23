"""Dynamic context-aware tool selector and confidence scorer."""

from __future__ import annotations

from typing import Any
from app.agent.intent import IntentClassification
from app.agent.query_analysis import QueryAnalysis
from app.agent.tools import TOOL_REGISTRY


def score_and_select_tools(
    intent_info: IntentClassification,
    query_info: QueryAnalysis,
    threshold: float = 0.5
) -> list[tuple[str, float]]:
    """Score all registered tools based on intent and filters, returning candidates above threshold."""
    scores = {}

    intent = intent_info.intent
    has_company = bool(intent_info.entities.get("company_name") or query_info.company_names)
    
    # Initialize default scores based on intent mapping
    if intent == "recommend_jobs":
        scores["recommend"] = 1.0
    elif intent == "search_jobs":
        scores["search_jobs"] = 1.0
        scores["recommend"] = 0.4
    elif intent == "company_research":
        scores["research_company"] = 1.0
        scores["score_company_attractiveness"] = 0.8
    elif intent == "fit_score":
        scores["score_company_fit"] = 1.0
    elif intent == "outreach":
        scores["generate_email"] = 1.0
    elif intent == "application_status":
        scores["list_applications"] = 1.0
        if has_company:
            scores["apply_to_company"] = 0.8
    elif intent == "alerts":
        scores["list_alerts"] = 1.0
    elif intent == "search_company":
        scores["list_companies"] = 1.0
        scores["search_jobs"] = 0.3
    elif intent == "follow_up":
        # Resolve contextual options
        scores["recommend"] = 0.6
        scores["list_applications"] = 0.4
        scores["research_company"] = 0.4
    elif intent == "memory_query":
        scores["remember_preference"] = 0.8

    # Apply parameter-matching adjustments
    for tool_name, score in list(scores.items()):
        tool_impl = TOOL_REGISTRY.get(tool_name)
        if not tool_impl:
            continue
            
        # Check if the tool requires parameters that we have or don't have
        schema = tool_impl.parameters_schema
        required = schema.get("required", [])
        
        # If tool requires company name and we have it, increase confidence
        if "company_name" in required:
            if has_company:
                scores[tool_name] = min(1.0, score + 0.1)
            else:
                # If required but we don't have it, penalize confidence
                scores[tool_name] = max(0.0, score - 0.4)

    # Filter by threshold and sort by score descending
    selected = [(name, s) for name, s in scores.items() if s >= threshold]
    return sorted(selected, key=lambda x: x[1], reverse=True)

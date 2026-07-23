"""Clarification engine checking missing parameters and formatting dialogs."""

from __future__ import annotations

from typing import Optional
from app.agent.intent import IntentClassification
from app.agent.query_analysis import QueryAnalysis
from app.agent.session import AgentSession


def check_and_clarify(
    intent_info: IntentClassification,
    query_info: QueryAnalysis,
    session: AgentSession
) -> Optional[str]:
    """Check for missing required parameters and return a clarification prompt, or None if satisfied.

    Avoids asking if session memory already resolves the parameter.
    """
    intent = intent_info.intent
    
    # 1. Company research or scoring requires a company name
    if intent in ("company_research", "fit_score", "outreach"):
        co_name = intent_info.entities.get("company_name") or (query_info.company_names[0] if query_info.company_names else None)
        
        # If missing in query, check if session memory has discussed companies
        if not co_name and session.discussed_companies:
            co_name = session.discussed_companies[-1]
            intent_info.entities["company_name"] = co_name
            query_info.company_names = [co_name]
            
        if not co_name:
            session.planning_metrics["clarifications_asked"] += 1
            if intent == "company_research":
                return "I see you want to research a company. Which company would you like to research?"
            elif intent == "fit_score":
                return "Please provide the name of the company you would like to evaluate compatibility against."
            else:
                return "Which company would you like to write an email outreach draft for?"

    return None

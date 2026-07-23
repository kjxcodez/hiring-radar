"""Multi-step Planning Engine constructing structured execution plans."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel
from app.agent.intent import IntentClassification
from app.agent.query_analysis import QueryAnalysis


class ExecutionPlan(BaseModel):
    """Structured plan for query execution."""
    goal: str
    intent: str
    steps: list[str]
    required_tools: list[str]
    estimated_steps: int


def create_execution_plan(
    intent_info: IntentClassification,
    query_info: QueryAnalysis,
    selected_tools: list[tuple[str, float]]
) -> ExecutionPlan:
    """Decompose the goal and intent into a structured plan with ordered steps."""
    intent = intent_info.intent
    tools_list = [name for name, _ in selected_tools]
    
    goal = f"Fulfill intent '{intent}'"
    steps = []
    
    if intent == "greeting":
        goal = "Acknowledge greeting and establish conversational rapport"
        steps = ["Formulate a friendly, helpful greeting response."]
    elif intent == "help":
        goal = "Display help options and platform usage commands"
        steps = ["List available command groups, search tips, and agent capabilities."]
    elif intent == "recommend_jobs":
        goal = "Compute desirability and compatibility matches matching the candidate resume"
        steps = [
            "Load active resume parameters.",
            "Run recommendations scoring using the 'recommend' tool.",
            "Format and present ranked match cards."
        ]
    elif intent == "search_jobs":
        titles = ", ".join(query_info.job_titles) if query_info.job_titles else "any title"
        locs = ", ".join(query_info.locations) if query_info.locations else "any location"
        goal = f"Search job openings matching roles ({titles}) in locations ({locs})"
        steps = [
            "Parse search filters (remote status, tech skills).",
            "Call 'search_jobs' to pull from Greenhouse, Lever, Ashby, etc.",
            "Display matching job listings."
        ]
    elif intent == "company_research":
        co_name = intent_info.entities.get("company_name") or (query_info.company_names[0] if query_info.company_names else "Unknown")
        goal = f"Perform deep corporate research on '{co_name}'"
        steps = [
            f"Query research database and web search details for '{co_name}'.",
            "Generate stacked technology and signals report.",
            "Rate company attractiveness metrics."
        ]
    elif intent == "fit_score":
        co_name = intent_info.entities.get("company_name") or (query_info.company_names[0] if query_info.company_names else "Unknown")
        goal = f"Compute fit scoring for '{co_name}'"
        steps = [
            "Load resume and compare keyword match properties.",
            "Compute fit score percentage.",
            "List matching and missing skills."
        ]
    elif intent == "outreach":
        co_name = intent_info.entities.get("company_name") or (query_info.company_names[0] if query_info.company_names else "Unknown")
        goal = f"Generate personalized outreach materials for '{co_name}'"
        steps = [
            "Load outreach template metadata.",
            "Inject company research variables to personalize.",
            "Display email subject and body drafts."
        ]
    elif intent == "application_status":
        goal = "Retrieve tracked job applications from the CRM database"
        steps = [
            "Read CRM tracking store.",
            "Format status fields and followup schedules."
        ]
    elif intent == "alerts":
        goal = "Retrieve active hiring monitoring events and system alerts"
        steps = [
            "Read monitoring repository.",
            "List top change detection events."
        ]
    elif intent == "search_company":
        goal = "Retrieve discovered companies database"
        steps = [
            "Query company repository.",
            "Format company profiles and role list."
        ]
    elif intent == "diagnostics":
        goal = "Run system environment and logging checks"
        steps = [
            "Verify environment settings.",
            "Validate logging isolation status."
        ]
    else:
        goal = "Resolve generic conversational reasoning query"
        steps = ["Formulate response based on history and context."]

    return ExecutionPlan(
        goal=goal,
        intent=intent,
        steps=steps,
        required_tools=tools_list,
        estimated_steps=len(steps)
    )

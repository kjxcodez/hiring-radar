"""Response Strategy Layer formatting replies depending on query intent."""

from __future__ import annotations

from typing import Any


def get_response_strategy_prompt(intent: str) -> str:
    """Return specific response styling directives for the LLM based on intent."""
    if intent == "recommend_jobs":
        return (
            "\nFormat the recommendations as a ranked list. For each match, display:\n"
            "- Company Name (bolded)\n"
            "- Overall compatibility score (as a percentage)\n"
            "- A bullet points summary of key selling/desirability indicators.\n"
            "Keep the output clean and prioritize visual scan-ability."
        )
    elif intent == "company_research":
        return (
            "\nFormat your response as a structured corporate research report containing:\n"
            "1. Company Overview & Domain Details\n"
            "2. Detected Technology Stack & Tools\n"
            "3. Desirability / Quality signals and employer indicators\n"
            "Ensure the details are strictly based on the provided research context."
        )
    elif intent == "application_status":
        return (
            "\nProvide a user-friendly summary of the tracked CRM applications. Mention status counts, "
            "highlight interviewing or offered roles, and note the next follow-up dates."
        )
    elif intent == "alerts":
        return (
            "\nSummarize the active monitoring events and change alerts. "
            "Explain what changed, which companies triggered updates, and why it requires attention."
        )
    elif intent == "greeting":
        return "\nRespond with a polite, conversational greeting. Introduce yourself as the Hiring Radar AI Agent."
    elif intent == "diagnostics":
        return "\nSummarize the health status of the environment, databases, and logging isolation checks in a technical summary."
    
    return "\nExplain the details clearly, using markdown formatting for tables, lists, and headers where helpful."

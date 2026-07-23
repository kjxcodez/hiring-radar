"""Grounding layer to verify and inject factual data context into LLM turns."""

from __future__ import annotations

import json
from typing import Any


def format_grounding_context(tool_name: str, tool_result: Any) -> str:
    """Format tool results into a structured system grounding context statement.

    Ensures the LLM explains the exact tool records rather than hallucinating details.
    """
    if not tool_result:
        return f"Grounding Context ({tool_name}): No records found in the database."

    if isinstance(tool_result, dict) and "error" in tool_result:
        return f"Grounding Context ({tool_name}) Error: {tool_result['error']}"

    if tool_name == "list_applications":
        lines = []
        for app in tool_result:
            co = app.get("company_name", "Unknown")
            role = app.get("job_title", "Role")
            status = app.get("status", "Unknown")
            followup = app.get("next_followup") or "None scheduled"
            lines.append(f"- Company: {co}, Role: {role}, Status: {status}, Next Followup: {followup}")
        return "\n".join(lines) if lines else "No job applications found."

    if tool_name == "list_alerts":
        lines = []
        for alert in tool_result:
            co = alert.get("company_name", "Unknown")
            ev = alert.get("event_type", "Unknown")
            detail = alert.get("details", "")
            lines.append(f"- Alert: {ev} at {co}. Details: {detail}")
        return "\n".join(lines) if lines else "No alerts found."

    if tool_name == "recommend":
        lines = []
        for idx, rec in enumerate(tool_result, 1):
            co = rec.get("name") or rec.get("company_name") or "Unknown"
            meta = rec.get("_recommendation_meta", {})
            score = int(meta.get("overall_score", 0) * 100)
            fit = int(meta.get("fit_score", 0) * 100)
            lines.append(f"{idx}. {co} (Overall: {score}%, Fit: {fit}%)")
        return "\n".join(lines) if lines else "No recommendations found."

    if tool_name == "list_companies":
        lines = []
        for idx, co in enumerate(tool_result, 1):
            name = co.get("name", "Unknown")
            domain = co.get("domain", "Unknown")
            jobs_count = len(co.get("jobs", []))
            lines.append(f"{idx}. {name} ({domain}) - {jobs_count} open jobs")
        return "\n".join(lines) if lines else "No companies found."

    try:
        return f"Grounding Context ({tool_name}):\n" + json.dumps(tool_result, indent=2)
    except Exception:
        return f"Grounding Context ({tool_name}): {str(tool_result)}"

"""In-memory session state manager for the Hiring Radar conversational agent."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any


class AgentSession:
    """Manages conversational session variables, statistics, and cache states."""

    def __init__(self) -> None:
        self.session_id: str = str(uuid.uuid4())
        self.start_time: datetime = datetime.utcnow()
        self.loaded_resume: Path | None = None
        
        # Statistics
        self.jobs_searched: int = 0
        self.companies_viewed: list[str] = []
        self.workflows_executed: list[str] = []
        self.tool_usage_statistics: dict[str, int] = {}
        
        # Contextual memories
        self.last_question: str | None = None
        self.discussed_companies: list[str] = []
        self.discussed_jobs: list[dict[str, Any]] = []
        
        # Recommendations & Decisions State
        self.last_recommendations: list[dict[str, Any]] = []
        self.accepted_recommendations: list[str] = []
        self.rejected_recommendations: list[str] = []
        
        # Extracted Preferences
        self.user_preferences: dict[str, Any] = {
            "locations": [],
            "salary_expectation": None,
            "remote_preferred": None,
            "technologies": [],
            "favorite_companies": []
        }
        
        # Planning & Validation Metrics (Goal 15)
        self.planning_metrics: dict[str, Any] = {
            "total_plans": 0,
            "successful_plans": 0,
            "failed_plans": 0,
            "clarifications_asked": 0,
            "unnecessary_llm_calls_avoided": 0,  # early exits
            "total_tool_calls_attempted": 0,
            "total_tool_calls_successful": 0,
            "average_tools_per_request": 0.0,
        }

    def record_tool_call(self, tool_name: str, arguments: dict[str, Any], successful: bool = True) -> None:
        """Log a tool execution in the session statistics and update discussed items."""
        self.tool_usage_statistics[tool_name] = self.tool_usage_statistics.get(tool_name, 0) + 1
        
        self.planning_metrics["total_tool_calls_attempted"] += 1
        if successful:
            self.planning_metrics["total_tool_calls_successful"] += 1
        
        if tool_name == "get_company":
            company_name = arguments.get("name")
            if company_name and company_name not in self.companies_viewed:
                self.companies_viewed.append(company_name)
            if company_name and company_name not in self.discussed_companies:
                self.discussed_companies.append(company_name)
        elif tool_name == "search_jobs":
            self.jobs_searched += 1
        elif tool_name == "score_company_fit":
            company_name = arguments.get("company_name")
            if company_name and company_name not in self.discussed_companies:
                self.discussed_companies.append(company_name)

    def record_workflow_execution(self, workflow_name: str) -> None:
        """Track execution of workflow pipelines."""
        if workflow_name not in self.workflows_executed:
            self.workflows_executed.append(workflow_name)

    def clear(self) -> None:
        """Reset the session variables."""
        self.loaded_resume = None
        self.jobs_searched = 0
        self.companies_viewed.clear()
        self.workflows_executed.clear()
        self.tool_usage_statistics.clear()
        self.last_question = None
        self.discussed_companies.clear()
        self.discussed_jobs.clear()
        self.last_recommendations.clear()
        self.accepted_recommendations.clear()
        self.rejected_recommendations.clear()
        self.user_preferences = {
            "locations": [],
            "salary_expectation": None,
            "remote_preferred": None,
            "technologies": [],
            "favorite_companies": []
        }
        self.planning_metrics = {
            "total_plans": 0,
            "successful_plans": 0,
            "failed_plans": 0,
            "clarifications_asked": 0,
            "unnecessary_llm_calls_avoided": 0,
            "total_tool_calls_attempted": 0,
            "total_tool_calls_successful": 0,
            "average_tools_per_request": 0.0,
        }

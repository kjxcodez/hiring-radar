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

    def record_tool_call(self, tool_name: str, arguments: dict[str, Any]) -> None:
        """Log a tool execution in the session statistics and update discussed items."""
        self.tool_usage_statistics[tool_name] = self.tool_usage_statistics.get(tool_name, 0) + 1
        
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

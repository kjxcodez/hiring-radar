from __future__ import annotations

from typing import Optional, Any
from app.models import Company
from app.repositories import CompanyRepository
from app.config import Settings
from app.ai import AiGateway


class ResearchService:
    """Service to perform deep AI/Github research on a company."""

    def __init__(
        self,
        company_repo: CompanyRepository,
        settings: Settings,
        ai_gateway: AiGateway | None = None,
        workflow_engine: Any = None,
    ):
        self.company_repo = company_repo
        self.settings = settings
        self.ai_gateway = ai_gateway
        self._workflow_engine = workflow_engine

    @property
    def workflow_engine(self) -> Any:
        """Resolve WorkflowEngine instance from CLI container context."""
        if self._workflow_engine is None:
            from app.cli.common import get_container
            self._workflow_engine = get_container().workflow_engine
        return self._workflow_engine

    def research(
        self,
        company_name: str,
        model: Optional[str] = None,
        dry_run: bool = False,
    ) -> Company:
        """Fetch Github profile details and call OpenRouter to perform deeper intelligence queries."""
        from app.workflows.context import WorkflowContext

        context = WorkflowContext(
            settings=self.settings,
            container=self.workflow_engine.container,
        )

        res = self.workflow_engine.run(
            "research",
            context=context,
            company_name=company_name,
            model=model,
            dry_run=dry_run,
        )

        # Context metadata will contain the researched company
        return res

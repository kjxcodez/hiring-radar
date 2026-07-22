from __future__ import annotations

from typing import Optional, Any
from app.repositories import CompanyRepository, ProfileRepository
from app.config import Settings
from app.services.resume import ResumeService


class RecommendationService:
    """Service to rank and recommend companies to apply to."""

    def __init__(
        self,
        company_repo: CompanyRepository,
        profile_repo: ProfileRepository,
        resume_service: ResumeService,
        settings: Settings,
        workflow_engine: Any = None,
    ):
        self.company_repo = company_repo
        self.profile_repo = profile_repo
        self.resume_service = resume_service
        self.settings = settings
        self._workflow_engine = workflow_engine

    @property
    def workflow_engine(self) -> Any:
        """Resolve WorkflowEngine instance from CLI container context."""
        if self._workflow_engine is None:
            from app.cli.common import get_container
            self._workflow_engine = get_container().workflow_engine
        return self._workflow_engine

    def get_recommendations(self, top: int = 5, resume_label: Optional[str] = None) -> list[dict[str, Any]]:
        """Rank and return recommendations based on overall company desirability and resume overlap."""
        from app.workflows.context import WorkflowContext

        context = WorkflowContext(
            settings=self.settings,
            container=self.workflow_engine.container,
        )

        res = self.workflow_engine.run(
            "recommend",
            context=context,
            top=top,
            resume_label=resume_label,
        )
        return res

from __future__ import annotations

from pathlib import Path
from typing import Optional, Any
from datetime import datetime

from app.models import Company
from app.repositories import CompanyRepository, ProfileRepository
from app.resume.parser import load_resume_text
from app.resume.versions import resolve_resume_version, list_resume_versions
from app.config import Settings
from app.ai import AiGateway


class ResumeService:
    """Service to score resumes and generate tailored resumes/suggestions."""

    def __init__(
        self,
        company_repo: CompanyRepository,
        profile_repo: ProfileRepository,
        settings: Settings,
        ai_gateway: AiGateway | None = None,
        workflow_engine: Any = None,
    ):
        self.company_repo = company_repo
        self.profile_repo = profile_repo
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

    def list_versions(self) -> list[str]:
        """Return a sorted list of all available resume stems in the resumes/ folder."""
        return list_resume_versions()

    def resolve_version_path(self, label: Optional[str]) -> Optional[Path]:
        """Find the file Path matching the provided version label, or default from settings."""
        if not label:
            return self.settings.resume_path

        p = Path(label)
        if p.exists() and p.is_file():
            return p

        return resolve_resume_version(label)

    def parse_resume(self, resume_path: Path) -> str:
        """Load text content from the resume (TXT or PDF)."""
        return load_resume_text(resume_path)

    def score_compatibility(
        self,
        company_name: str,
        resume_label: Optional[str] = None,
        model: Optional[str] = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Compare resume text against jobs to determine match ratings, missing skills, and metrics."""
        from app.workflows.context import WorkflowContext

        context = WorkflowContext(
            settings=self.settings,
            container=self.workflow_engine.container,
        )

        res = self.workflow_engine.run(
            "resume",
            context=context,
            company_name=company_name,
            resume_label=resume_label,
            model=model,
            dry_run=dry_run,
        )
        return res

    def suggest_tailoring(
        self,
        company_name: str,
        resume_label: Optional[str] = None,
        model: Optional[str] = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Generate keywords, projects, objective highlights, and reordering suggestions for tailoring."""
        from app.workflows.context import WorkflowContext

        context = WorkflowContext(
            settings=self.settings,
            container=self.workflow_engine.container,
        )

        res = self.workflow_engine.run(
            "resume_tailor",
            context=context,
            company_name=company_name,
            resume_label=resume_label,
            model=model,
            dry_run=dry_run,
        )
        return res

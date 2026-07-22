from __future__ import annotations

from typing import Optional, Callable, Any
from app.repositories import CompanyRepository
from app.config import Settings
from app.ai import AiGateway


class ScrapingService:
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

    def scrape(
        self,
        company_filter: Optional[str] = None,
        force: bool = False,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> dict[str, int]:
        """Fetch career-page details and extract contact hints for each company in the database."""
        from app.workflows.progress import WorkflowProgress
        from app.workflows.context import WorkflowContext

        progress = WorkflowProgress()
        if progress_callback:
            def _adapt(event_type: str, data: dict[str, Any]) -> None:
                if event_type == "advance":
                    co_name = data.get("co_name")
                    idx = data.get("idx")
                    total = data.get("total")
                    if co_name is not None and idx is not None and total is not None:
                        progress_callback(co_name, idx, total)

            progress.subscribe(_adapt)

        context = WorkflowContext(
            settings=self.settings,
            container=self.workflow_engine.container,
            progress=progress,
        )

        res = self.workflow_engine.run(
            "discover",
            context=context,
            company_filter=company_filter,
            force=force,
            skip_discover=True,  # Bypass query phase
            skip_scrape=False,   # Run scraping logic
        )
        return res if isinstance(res, dict) else {"processed": 0, "skipped": 0, "new_emails": 0, "failures": 0}

    def enrich(
        self,
        model: Optional[str] = None,
        dry_run: bool = False,
        force: bool = False,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> dict[str, Any]:
        """Generate AI summaries and talking points for each company via an LLM."""
        from app.workflows.progress import WorkflowProgress
        from app.workflows.context import WorkflowContext

        progress = WorkflowProgress()
        if progress_callback:
            def _adapt(event_type: str, data: dict[str, Any]) -> None:
                if event_type == "advance":
                    co_name = data.get("co_name")
                    idx = data.get("idx")
                    total = data.get("total")
                    if co_name is not None and idx is not None and total is not None:
                        progress_callback(co_name, idx, total)

            progress.subscribe(_adapt)

        context = WorkflowContext(
            settings=self.settings,
            container=self.workflow_engine.container,
            progress=progress,
        )

        res = self.workflow_engine.run(
            "enrich",
            context=context,
            model=model,
            dry_run=dry_run,
            force=force,
        )
        return res

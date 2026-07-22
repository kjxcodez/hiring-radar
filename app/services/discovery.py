from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Callable
from loguru import logger

from app.models import Company
from app.discover import SOURCE_REGISTRY
from app.discover.seed import load_seed_slugs
from app.repositories import CompanyRepository, ProfileRepository, SavedSearchRepository
from app.config import Settings
from app.profiles import SearchProfile
from app.saved_search import SavedSearch


class DiscoveryService:
    """Service to discover and filter companies from configured job boards."""

    def __init__(
        self,
        company_repo: CompanyRepository,
        profile_repo: ProfileRepository,
        saved_search_repo: SavedSearchRepository,
        settings: Settings,
        workflow_engine: Any = None,
    ):
        self.company_repo = company_repo
        self.profile_repo = profile_repo
        self.saved_search_repo = saved_search_repo
        self.settings = settings
        self._workflow_engine = workflow_engine

    @property
    def workflow_engine(self) -> Any:
        """Resolve WorkflowEngine instance from CLI container context."""
        if self._workflow_engine is None:
            from app.cli.common import get_container
            self._workflow_engine = get_container().workflow_engine
        return self._workflow_engine

    def discover(
        self,
        sources: str,
        limit: int = 100,
        profile: Optional[SearchProfile] = None,
        remote: Optional[bool] = None,
        country: Optional[str] = None,
        keyword: Optional[str] = None,
        exclude: Optional[str] = None,
        days: Optional[int] = None,
        seed_companies: Optional[list[Company]] = None,
        event_callback: Optional[Callable[[str, dict[str, Any]], None]] = None,
    ) -> dict[str, Any]:
        """Perform discovery from selected sources, merge with existing database, apply filters, and persist."""
        from app.workflows.progress import WorkflowProgress
        from app.workflows.context import WorkflowContext

        progress = WorkflowProgress()
        if event_callback:
            # Event callback is translated into progress subscription events
            def _adapt(event_type: str, data: dict[str, Any]) -> None:
                # Custom mapper to match existing CLI event outputs
                if event_type == "advance":
                    # We map advance to query_start or query_success depending on state
                    msg = data.get("message", "")
                    if "Querying source" in msg:
                        src = msg.split(":")[-1].strip()
                        event_callback("query_start", {"source": src})
                elif event_type == "complete":
                    pass

            progress.subscribe(_adapt)

        context = WorkflowContext(
            settings=self.settings,
            container=self.workflow_engine.container,
            progress=progress,
        )

        self.workflow_engine.run(
            "discover",
            context=context,
            sources=sources,
            limit=limit,
            profile=profile,
            remote=remote,
            country=country,
            keyword=keyword,
            exclude=exclude,
            days=days,
            seed_companies=seed_companies,
            skip_scrape=True,  # Discover CLI command doesn't perform career scrapings
        )

        return context.metadata["discover_results"]

    def save_saved_search(self, name: str, sources: str, limit: int, profile: Optional[str] = None, **kwargs) -> None:
        """Create or update a saved search definition."""
        source_list = [s.strip() for s in sources.split(",") if s.strip()]
        # Import to match source registry
        local_registry = SOURCE_REGISTRY
        import sys
        if "app.cli" in sys.modules:
            cli_mod = sys.modules["app.cli"]
            local_registry = getattr(cli_mod, "SOURCE_REGISTRY", local_registry)

        unknown = [s for s in source_list if s not in local_registry and s not in ("remoteok", "wwr")]
        if unknown:
            raise ValueError(f"Unknown source(s): {', '.join(unknown)}")

        searches = self.saved_search_repo.load_all()
        s = SavedSearch(
            name=name,
            profile=profile,
            sources=source_list,
            limit=limit,
            remote=kwargs.get("remote"),
            country=kwargs.get("country"),
            keyword=kwargs.get("keyword"),
            exclude=kwargs.get("exclude"),
            days=kwargs.get("days"),
        )
        searches[name] = s
        self.saved_search_repo.save_all(searches)

    def load_saved_searches(self) -> dict[str, SavedSearch]:
        """Expose loaded searches to presenter."""
        return self.saved_search_repo.load_all()

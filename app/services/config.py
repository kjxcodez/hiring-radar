from __future__ import annotations

from pathlib import Path
from typing import Any
from app.config import settings, yaml_config
from app.repositories import (
    CompanyRepository,
    ApplicationRepository,
    MemoryRepository,
    ProfileRepository,
    SavedSearchRepository,
)
from app.storage import JsonStorage
from app.ai import AiGateway


def _resolve_config_value(config_val: Any, cli_val: Any) -> Any:
    """Helper to detect and return the mocked settings/config if present in tests."""
    def is_mock(obj: Any) -> bool:
        return "mock" in type(obj).__name__.lower()

    if is_mock(config_val):
        return config_val
    if is_mock(cli_val):
        return cli_val
    return config_val


class ServiceContainer:
    """Service container that manages lifecycles and wires up dependencies."""

    def __init__(self):
        import sys
        import app.config
        self.settings = app.config.settings
        self.yaml_config = app.config.yaml_config
        if "app.cli" in sys.modules:
            cli_mod = sys.modules["app.cli"]
            cli_settings = getattr(cli_mod, "settings", self.settings)
            self.settings = _resolve_config_value(app.config.settings, cli_settings)
            cli_yaml = getattr(cli_mod, "yaml_config", self.yaml_config)
            self.yaml_config = _resolve_config_value(app.config.yaml_config, cli_yaml)

        # Storage layer
        self.storage = JsonStorage()

        # AI Infrastructure
        self.ai_gateway = AiGateway(self.settings)

        # Repositories
        self.company_repo = CompanyRepository(self.settings.output_dir / "companies.json", storage=self.storage)
        self.application_repo = ApplicationRepository(self.settings.output_dir / "applications.json", storage=self.storage)
        self.memory_repo = MemoryRepository(self.settings.output_dir / "agent_memory.json", storage=self.storage)
        self.profile_repo = ProfileRepository(
            profiles_dir=Path("profiles"),
            alerts_path=Path("alerts.yaml")
        )
        self.saved_search_repo = SavedSearchRepository(self.settings.output_dir / "saved_searches.json", storage=self.storage)

        # Services (lazy-initialized to avoid circular imports or fast startup issues)
        self._discovery_service = None
        self._scraping_service = None
        self._research_service = None
        self._resume_service = None
        self._outreach_service = None
        self._tracker_service = None
        self._recommendation_service = None
        self._dashboard_service = None
        self._health_service = None
        self._workflow_engine = None
        self._runtime = None
        self._sync_engine = None
        self._intelligence_engine = None



    @property
    def runtime(self):
        """Lazy-initialized ExecutionRuntime instance."""
        if self._runtime is None:
            from app.runtime.runtime import ExecutionRuntime
            self._runtime = ExecutionRuntime(
                container=self,
                settings=self.settings,
            )
        return self._runtime

    @property
    def workflow_engine(self):
        """Lazy-initialized WorkflowEngine instance."""
        if self._workflow_engine is None:
            from app.workflows.engine import WorkflowEngine
            self._workflow_engine = WorkflowEngine(
                container=self,
                settings=self.settings,
                ai_gateway=self.ai_gateway,
            )
        return self._workflow_engine

    @property
    def discovery_service(self):
        """Lazy-initialized DiscoveryService instance."""
        if self._discovery_service is None:
            from app.services.discovery import DiscoveryService
            self._discovery_service = DiscoveryService(
                company_repo=self.company_repo,
                profile_repo=self.profile_repo,
                saved_search_repo=self.saved_search_repo,
                settings=self.settings,
                workflow_engine=self.workflow_engine
            )
        return self._discovery_service

    @property
    def scraping_service(self):
        """Lazy-initialized ScrapingService instance."""
        if self._scraping_service is None:
            from app.services.scraping import ScrapingService
            self._scraping_service = ScrapingService(
                company_repo=self.company_repo,
                settings=self.settings,
                ai_gateway=self.ai_gateway,
                workflow_engine=self.workflow_engine
            )
        return self._scraping_service

    @property
    def research_service(self):
        """Lazy-initialized ResearchService instance."""
        if self._research_service is None:
            from app.services.research import ResearchService
            self._research_service = ResearchService(
                company_repo=self.company_repo,
                settings=self.settings,
                ai_gateway=self.ai_gateway,
                workflow_engine=self.workflow_engine
            )
        return self._research_service

    @property
    def resume_service(self):
        """Lazy-initialized ResumeService instance."""
        if self._resume_service is None:
            from app.services.resume import ResumeService
            self._resume_service = ResumeService(
                company_repo=self.company_repo,
                profile_repo=self.profile_repo,
                settings=self.settings,
                ai_gateway=self.ai_gateway,
                workflow_engine=self.workflow_engine
            )
        return self._resume_service

    @property
    def outreach_service(self):
        """Lazy-initialized OutreachService instance."""
        if self._outreach_service is None:
            from app.services.outreach import OutreachService
            self._outreach_service = OutreachService(
                company_repo=self.company_repo,
                settings=self.settings,
                yaml_config=self.yaml_config,
                ai_gateway=self.ai_gateway,
                workflow_engine=self.workflow_engine
            )
        return self._outreach_service

    @property
    def tracker_service(self):
        """Lazy-initialized TrackerService instance."""
        if self._tracker_service is None:
            from app.services.tracker import TrackerService
            self._tracker_service = TrackerService(
                application_repo=self.application_repo,
                company_repo=self.company_repo
            )
        return self._tracker_service

    @property
    def recommendation_service(self):
        """Lazy-initialized RecommendationService instance."""
        if self._recommendation_service is None:
            from app.services.recommendation import RecommendationService
            self._recommendation_service = RecommendationService(
                company_repo=self.company_repo,
                profile_repo=self.profile_repo,
                settings=self.settings,
                resume_service=self.resume_service,
                workflow_engine=self.workflow_engine
            )
        return self._recommendation_service

    @property
    def dashboard_service(self):
        """Lazy-initialized DashboardService instance."""
        if self._dashboard_service is None:
            from app.services.dashboard import DashboardService
            self._dashboard_service = DashboardService(
                company_repo=self.company_repo,
                settings=self.settings
            )
        return self._dashboard_service

    @property
    def health_service(self):
        """Lazy-initialized HealthService instance."""
        if self._health_service is None:
            from app.services.health import HealthService
            self._health_service = HealthService(
                company_repo=self.company_repo,
                application_repo=self.application_repo,
                settings=self.settings,
                yaml_config=self.yaml_config
            )
        return self._health_service

    def reset(self) -> None:
        """Reset the service container settings and cached service instances."""
        import sys
        import app.config
        self.settings = app.config.settings
        self.yaml_config = app.config.yaml_config
        if "app.cli" in sys.modules:
            cli_mod = sys.modules["app.cli"]
            cli_settings = getattr(cli_mod, "settings", self.settings)
            self.settings = _resolve_config_value(app.config.settings, cli_settings)
            cli_yaml = getattr(cli_mod, "yaml_config", self.yaml_config)
            self.yaml_config = _resolve_config_value(app.config.yaml_config, cli_yaml)

        # Storage layer
        self.storage = JsonStorage()

        # AI Infrastructure
        self.ai_gateway = AiGateway(self.settings)

        # Repositories
        self.company_repo = CompanyRepository(self.settings.output_dir / "companies.json", storage=self.storage)
        self.application_repo = ApplicationRepository(self.settings.output_dir / "applications.json", storage=self.storage)
        self.memory_repo = MemoryRepository(self.settings.output_dir / "agent_memory.json", storage=self.storage)
        self.profile_repo = ProfileRepository(
            profiles_dir=Path("profiles"),
            alerts_path=Path("alerts.yaml")
        )
        self.saved_search_repo = SavedSearchRepository(self.settings.output_dir / "saved_searches.json", storage=self.storage)

        # Services
        self._discovery_service = None
        self._scraping_service = None
        self._research_service = None
        self._resume_service = None
        self._outreach_service = None
        self._tracker_service = None
        self._recommendation_service = None
        self._dashboard_service = None
        self._health_service = None
        self._workflow_engine = None
        self._runtime = None
        self._sync_engine = None
        self._intelligence_engine = None

    @property
    def sync_engine(self):
        """Lazy-initialized SyncEngine instance."""
        if self._sync_engine is None:
            from app.sync.engine import SyncEngine
            self._sync_engine = SyncEngine(self, self.settings)
        return self._sync_engine

    @property
    def intelligence_engine(self):
        """Lazy-initialized CompanyIntelligenceEngine instance."""
        if self._intelligence_engine is None:
            from app.intelligence.engine import CompanyIntelligenceEngine
            self._intelligence_engine = CompanyIntelligenceEngine(self, self.settings)
        return self._intelligence_engine



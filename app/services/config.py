from __future__ import annotations

from pathlib import Path
from app.config import settings, yaml_config
from app.repositories import CompanyRepository, ApplicationRepository, MemoryRepository, ProfileRepository

class ServiceContainer:
    def __init__(self):
        import app.config
        self.settings = app.config.settings
        self.yaml_config = app.config.yaml_config

        # Repositories
        self.company_repo = CompanyRepository(self.settings.output_dir / "companies.json")
        self.application_repo = ApplicationRepository(self.settings.output_dir / "applications.json")
        self.memory_repo = MemoryRepository(self.settings.output_dir / "agent_memory.json")
        self.profile_repo = ProfileRepository(
            profiles_dir=Path("profiles"),
            alerts_path=Path("alerts.yaml")
        )

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

    @property
    def discovery_service(self):
        if self._discovery_service is None:
            from app.services.discovery import DiscoveryService
            self._discovery_service = DiscoveryService(
                company_repo=self.company_repo,
                profile_repo=self.profile_repo,
                settings=self.settings
            )
        return self._discovery_service

    @property
    def scraping_service(self):
        if self._scraping_service is None:
            from app.services.scraping import ScrapingService
            self._scraping_service = ScrapingService(
                company_repo=self.company_repo,
                settings=self.settings
            )
        return self._scraping_service

    @property
    def research_service(self):
        if self._research_service is None:
            from app.services.research import ResearchService
            self._research_service = ResearchService(
                company_repo=self.company_repo,
                settings=self.settings
            )
        return self._research_service

    @property
    def resume_service(self):
        if self._resume_service is None:
            from app.services.resume import ResumeService
            self._resume_service = ResumeService(
                company_repo=self.company_repo,
                profile_repo=self.profile_repo,
                settings=self.settings
            )
        return self._resume_service

    @property
    def outreach_service(self):
        if self._outreach_service is None:
            from app.services.outreach import OutreachService
            self._outreach_service = OutreachService(
                company_repo=self.company_repo,
                settings=self.settings,
                yaml_config=self.yaml_config
            )
        return self._outreach_service

    @property
    def tracker_service(self):
        if self._tracker_service is None:
            from app.services.tracker import TrackerService
            self._tracker_service = TrackerService(
                application_repo=self.application_repo,
                company_repo=self.company_repo
            )
        return self._tracker_service

    @property
    def recommendation_service(self):
        if self._recommendation_service is None:
            from app.services.recommendation import RecommendationService
            self._recommendation_service = RecommendationService(
                company_repo=self.company_repo,
                profile_repo=self.profile_repo,
                settings=self.settings
            )
        return self._recommendation_service

    @property
    def dashboard_service(self):
        if self._dashboard_service is None:
            from app.services.dashboard import DashboardService
            self._dashboard_service = DashboardService(
                company_repo=self.company_repo,
                settings=self.settings
            )
        return self._dashboard_service

    @property
    def health_service(self):
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
        import app.config
        self.settings = app.config.settings
        self.yaml_config = app.config.yaml_config

        # Repositories
        self.company_repo = CompanyRepository(self.settings.output_dir / "companies.json")
        self.application_repo = ApplicationRepository(self.settings.output_dir / "applications.json")
        self.memory_repo = MemoryRepository(self.settings.output_dir / "agent_memory.json")
        self.profile_repo = ProfileRepository(
            profiles_dir=Path("profiles"),
            alerts_path=Path("alerts.yaml")
        )

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


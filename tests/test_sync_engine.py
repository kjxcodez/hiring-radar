"""Unit tests for the Synchronization Engine."""

from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models import Company, JobPosting
from app.repositories import CompanyRepository
from app.services.config import ServiceContainer
from app.storage import JsonStorage
from app.sync.engine import SyncEngine


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


def _make_company(name: str, domain: str, jobs: list[JobPosting] = None) -> Company:
    return Company(
        name=name,
        domain=domain,
        jobs=jobs or [],
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )


def _make_job(title: str, url: str) -> JobPosting:
    return JobPosting(
        job_title=title,
        job_url=url,
        source="mock_provider",
    )


class TestSyncEngine:

    @patch("app.discovery.registry.ProviderRegistry.get")
    def test_sync_all_metrics(self, mock_get_provider, temp_dir):
        from unittest.mock import AsyncMock

        # Set up mock provider
        mock_provider = MagicMock()
        mock_get_provider.return_value = mock_provider
        
        co1 = _make_company("Stripe", "stripe.com", [_make_job("Backend Dev", "https://stripe.com/1")])
        mock_provider.discover = AsyncMock(return_value=[co1])

        # Prepare ServiceContainer
        container = ServiceContainer()
        companies_file = temp_dir / "companies.json"
        
        storage = JsonStorage()
        container.company_repo = CompanyRepository(companies_file, storage=storage)
        container.settings.output_dir = temp_dir

        engine = SyncEngine(container, container.settings)
        engine.cooldown_seconds = 0.0  # disable cooldown for testing

        # Run first sync (cold run)
        metrics = asyncio.run(engine.sync_provider("mock_provider", ["stripe"], 10))
        assert metrics.companies_discovered == 1
        assert metrics.jobs_added == 1
        assert metrics.cache_misses == 1

        # Check companies saved
        saved = container.company_repo.load_all()
        assert len(saved) == 1
        assert saved[0].name == "Stripe"
        assert len(saved[0].jobs) == 1

        # Run second sync (hot run, same data)
        metrics2 = asyncio.run(engine.sync_provider("mock_provider", ["stripe"], 10))
        assert metrics2.companies_discovered == 0
        assert metrics2.jobs_added == 0
        assert metrics2.cache_hits == 1  # checksum match cache hit

        # Run third sync (with added job)
        co2 = _make_company("Stripe", "stripe.com", [
            _make_job("Backend Dev", "https://stripe.com/1"),
            _make_job("Frontend Dev", "https://stripe.com/2")
        ])
        mock_provider.discover = AsyncMock(return_value=[co2])

        metrics3 = asyncio.run(engine.sync_provider("mock_provider", ["stripe"], 10))
        assert metrics3.companies_updated == 1
        assert metrics3.jobs_added == 1
        
        saved3 = container.company_repo.load_all()
        assert len(saved3[0].jobs) == 2

        # Run fourth sync (with job removed -> soft delete)
        co3 = _make_company("Stripe", "stripe.com", [
            _make_job("Frontend Dev", "https://stripe.com/2")
        ])
        mock_provider.discover = AsyncMock(return_value=[co3])


        metrics4 = asyncio.run(engine.sync_provider("mock_provider", ["stripe"], 10))
        assert metrics4.jobs_removed == 1

        saved4 = container.company_repo.load_all()
        assert len(saved4[0].jobs) == 1
        assert saved4[0].jobs[0].job_title == "Frontend Dev"
        # Confirm soft deletion note exists
        assert any("job_removed: Backend Dev" in n for n in saved4[0].notes)

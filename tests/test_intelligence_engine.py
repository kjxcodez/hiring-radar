"""Unit tests for the Company Intelligence enrichment engine."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.models import Company, JobPosting
from app.repositories import CompanyRepository
from app.services.config import ServiceContainer
from app.storage import JsonStorage
from app.intelligence.engine import CompanyIntelligenceEngine


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
        source="test_provider",
    )


class TestIntelligenceEngine:

    def test_enrichment_flow_and_cache(self, temp_dir):
        # Prepare mock AI Gateway
        mock_gateway = MagicMock()
        mock_gateway.complete.return_value = (
            "{"
            '  "executive_summary": "Mock Stripe executive summary.",'
            '  "engineering_summary": "Using Ruby, Go, and Python.",'
            '  "why_join": "Great team.",'
            '  "potential_risks": "Fierce fintech competition.",'
            '  "resume_keywords": ["python", "payments"],'
            '  "outreach_talking_points": ["Point 1", "Point 2"]'
            "}"
        )

        container = ServiceContainer()
        container.ai_gateway = mock_gateway
        container.settings.output_dir = temp_dir
        container.company_repo = CompanyRepository(temp_dir / "companies.json", storage=JsonStorage())

        engine = CompanyIntelligenceEngine(container, container.settings)

        co = _make_company(
            "Stripe",
            "stripe.com",
            [_make_job("Senior Engineer (Python)", "https://stripe.com/1")]
        )
        co.description = "We offer a payments platform. We use Python and AWS Cloud."

        # Run Enrichment (force=True to skip crawler networking mock check)
        # Mock client to avoid real http calls
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "We offer a payments platform. We use Python and AWS Cloud."
        mock_client.get.return_value = mock_response

        enriched = engine.enrich_company(co, client=mock_client, force=True)


        assert enriched.intelligence is not None
        assert "Python" in enriched.intelligence.engineering.languages
        assert "AWS" in enriched.intelligence.engineering.cloud
        assert enriched.ai_summary == "Mock Stripe executive summary."
        assert "Point 1" in enriched.ai_talking_points

        # Cache key should have been calculated
        assert enriched.intelligence.cache_key is not None

        # Verify calls to gateway happened
        assert mock_gateway.complete.call_count == 1

        # Reset mock call count and run sync/enrichment again without force -> should hit cache
        mock_gateway.complete.reset_mock()
        engine.enrich_company(enriched, client=mock_client, force=False)
        assert mock_gateway.complete.call_count == 0  # Cache hit!

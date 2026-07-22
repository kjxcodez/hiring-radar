"""Unit tests for the complete Job Recommendation Engine flow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.models import Company, JobPosting
from app.repositories import CompanyRepository
from app.services.config import ServiceContainer
from app.storage import JsonStorage
from app.recommendation.profile import CandidateProfile
from app.recommendation.engine import RecommendationEngine


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


def test_recommendation_engine_full_flow(temp_dir):
    # Setup mock gateway
    mock_gateway = MagicMock()
    mock_gateway.complete.return_value = (
        "{"
        '  "why_fit": "Fits because of Python skills.",'
        '  "strengths": ["Python"],'
        '  "weaknesses": ["Docker"],'
        '  "missing_skills_analysis": "Missing Docker infrastructure experience.",'
        '  "resume_improvements": ["Add Docker project details"],'
        '  "interview_prep_tips": ["Prepare Docker scaling answers"],'
        '  "study_roadmap": ["Learn Docker containers"],'
        '  "outreach_talking_points": ["I love building with Python."]'
        "}"
    )

    container = ServiceContainer()
    container.ai_gateway = mock_gateway
    container.settings.output_dir = temp_dir
    container.company_repo = CompanyRepository(temp_dir / "companies.json", storage=JsonStorage())

    # Add mock company with jobs
    company = Company(
        name="Stripe",
        domain="stripe.com",
        description="We use Python.",
        jobs=[
            JobPosting(
                job_title="Senior Python Engineer",
                job_url="https://stripe.com/1",
                source="greenhouse",
            )
        ],
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )
    container.company_repo.save_all([company])

    engine = RecommendationEngine(container, container.settings)

    cand = CandidateProfile(
        skills=["Python"],
        years_experience=5.0,
    )

    # 1. Run Pipeline
    recs = engine.recommend(cand, force=True)

    assert len(recs) == 1
    assert recs[0]["company_name"] == "Stripe"
    assert recs[0]["score"] == 100.0  # Perfect fit on skills/experience
    assert recs[0]["explanation"]["why_fit"] == "Fits because of Python skills."

    # Cache should have saved
    assert recs[0]["cache_key"] is not None
    assert mock_gateway.complete.call_count == 1

    # 2. Run Pipeline again without force -> Cache hit
    mock_gateway.complete.reset_mock()
    recs2 = engine.recommend(cand, force=False)
    assert len(recs2) == 1
    assert mock_gateway.complete.call_count == 0  # No AI explanation call (cached!)

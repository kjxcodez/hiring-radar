"""Unit tests for the OutreachEngine application and CRM pipeline."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.models import Company, JobPosting
from app.repositories import CompanyRepository
from app.repositories.application import ApplicationRepository
from app.services.config import ServiceContainer
from app.storage import JsonStorage
from app.outreach.engine import OutreachEngine
from app.recommendation.profile import CandidateProfile


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    return tmp_path


def test_outreach_engine_pipeline(temp_dir):
    # Setup mock gateway to return custom JSON strings for different templates
    mock_gateway = MagicMock()
    
    def mock_complete(prompt_id, user_content, temperature, use_cache):
        if "cover_letter" in prompt_id:
            return (
                "{"
                '  "salutation": "Dear Stripe Team,",'
                '  "opening": "Expressing my interest.",'
                '  "motivation": "Stripe is cool.",'
                '  "technical_alignment": "Aligns with systems skills.",'
                '  "closing": "Looking forward.",'
                '  "full_letter": "Cover Letter Content"'
                "}"
            )
        elif "linkedin" in prompt_id:
            return '{"content": "Hi recruiter, let\'s chat!"}'
        elif "referral" in prompt_id:
            return '{"content": "Hi connection, refer me please!"}'
        elif "outreach_email" in prompt_id:
            return '{"subject": "Apply to Stripe", "body": "Email body content"}'
        return "{}"

    mock_gateway.complete.side_effect = mock_complete

    # Create service container
    container = ServiceContainer()
    container.ai_gateway = mock_gateway
    container.settings.output_dir = temp_dir
    container.company_repo = CompanyRepository(temp_dir / "companies.json", storage=JsonStorage())
    container.application_repo = ApplicationRepository(temp_dir / "applications.json", storage=JsonStorage())

    # Add mock company
    company = Company(
        name="Stripe",
        domain="stripe.com",
        description="Online payments infrastructure.",
        jobs=[
            JobPosting(
                job_title="Senior Infrastructure Engineer",
                job_url="https://stripe.com/1",
                source="greenhouse",
            )
        ],
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )
    container.company_repo.save_all([company])

    engine = OutreachEngine(container)

    cand = CandidateProfile(
        skills=["Python", "Systems"],
        years_experience=5.0,
    )

    # Execute preparation pipeline
    app = engine.prepare_application(company_name="Stripe", candidate=cand)

    assert app.company_key == "stripe.com"
    assert app.status == "Prepared"
    assert app.cover_letter_version == "Cover Letter Content"
    assert len(app.messages) == 3
    assert app.messages[0].channel == "email"
    assert app.messages[1].channel == "linkedin"
    assert app.messages[2].channel == "referral"
    assert len(app.followup_schedule) == 4
    assert len(app.timeline) == 1
    assert app.timeline[0].event == "Application created"

    # Verify persistence
    apps_loaded = container.application_repo.load_all()
    assert "stripe.com" in apps_loaded
    assert apps_loaded["stripe.com"].cover_letter_version == "Cover Letter Content"

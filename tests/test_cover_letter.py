"""Unit tests for the CoverLetterGenerator using mock AI completions."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from app.models import Company, JobPosting
from app.recommendation.profile import CandidateProfile
from app.outreach.cover_letter import CoverLetterGenerator


def test_cover_letter_generator_mock_ai():
    mock_gateway = MagicMock()
    mock_gateway.complete.return_value = (
        "{"
        '  "salutation": "Dear Stripe Team,",'
        '  "opening": "I want to apply to Stripe.",'
        '  "motivation": "Stripe is great.",'
        '  "technical_alignment": "I code in Python.",'
        '  "closing": "Thanks.",'
        '  "full_letter": "Dear Stripe Team, I want to apply to Stripe. Stripe is great. I code in Python. Thanks."'
        "}"
    )

    cand = CandidateProfile(skills=["Python"])
    job = JobPosting(job_title="Developer", job_url="http://co.com", source="greenhouse")
    company = Company(name="Stripe", domain="stripe.com", discovered_at=datetime.utcnow(), last_updated=datetime.utcnow())

    letter = CoverLetterGenerator.generate(cand, job, company, mock_gateway)
    assert letter["salutation"] == "Dear Stripe Team,"
    assert "Python" in letter["technical_alignment"]

"""Unit tests for the ReferralRequestGenerator using mock AI completions."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from app.models import Company, JobPosting
from app.recommendation.profile import CandidateProfile
from app.outreach.referral import ReferralRequestGenerator


def test_referral_request_generator_mock_ai():
    mock_gateway = MagicMock()
    mock_gateway.complete.return_value = (
        "{"
        '  "content": "Hi there, saw you work at Stripe. Let\'d connect!"'
        "}"
    )

    cand = CandidateProfile(skills=["Python"])
    job = JobPosting(job_title="Developer", job_url="http://co.com", source="greenhouse")
    company = Company(name="Stripe", domain="stripe.com", discovered_at=datetime.utcnow(), last_updated=datetime.utcnow())

    msg = ReferralRequestGenerator.generate(cand, job, company, mock_gateway)
    assert "Stripe" in msg["content"]

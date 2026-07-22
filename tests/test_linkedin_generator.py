"""Unit tests for the LinkedInMessageGenerator using mock AI completions."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from app.models import Company, JobPosting
from app.recommendation.profile import CandidateProfile
from app.outreach.linkedin import LinkedInMessageGenerator


def test_linkedin_message_generator_mock_ai():
    mock_gateway = MagicMock()
    mock_gateway.complete.return_value = (
        "{"
        '  "content": "Hi, I\'d love to chat about engineering roles at Stripe." '
        "}"
    )

    cand = CandidateProfile(skills=["Python"])
    job = JobPosting(job_title="Developer", job_url="http://co.com", source="greenhouse")
    company = Company(name="Stripe", domain="stripe.com", discovered_at=datetime.utcnow(), last_updated=datetime.utcnow())

    msg = LinkedInMessageGenerator.generate(cand, job, company, mock_gateway)
    assert "chat" in msg["content"]
    assert len(msg["content"]) < 300

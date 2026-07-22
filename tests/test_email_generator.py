"""Unit tests for the EmailGenerator helper."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock
from app.models import Company, JobPosting
from app.recommendation.profile import CandidateProfile
from app.outreach.email import generate_email


def test_email_generator_dry_run():
    company = Company(name="Stripe", domain="stripe.com", discovered_at=datetime.utcnow(), last_updated=datetime.utcnow())
    res = generate_email(company, dry_run=True)
    assert "subject" in res
    assert "body" in res

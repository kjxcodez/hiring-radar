"""Unit tests for the resume tailoring module."""

from __future__ import annotations

from datetime import datetime
from app.models import Company
from app.resume.suggestions import suggest_resume_tailoring


def test_resume_tailoring_dry_run():
    company = Company(
        name="Stripe",
        domain="stripe.com",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )
    # Dry run returns safe default dict
    res = suggest_resume_tailoring(company, "Experienced systems engineer.", dry_run=True)
    assert "missing_keywords" in res
    assert "projects_to_emphasize" in res

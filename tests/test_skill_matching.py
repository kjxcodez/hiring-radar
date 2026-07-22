"""Unit tests for the SkillMatcher module."""

from __future__ import annotations

from datetime import datetime

from app.models import Company, JobPosting
from app.recommendation.profile import CandidateProfile
from app.recommendation.matching import SkillMatcher


def test_skill_matcher_overlap():
    candidate = CandidateProfile(skills=["Python", "React", "Docker"])
    job = JobPosting(job_title="Senior Python Developer", job_url="https://stripe.com/1", source="greenhouse")
    company = Company(
        name="Stripe",
        domain="stripe.com",
        description="We build payment infrastructure. Looking for React and backend developers.",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )

    res = SkillMatcher.match(candidate, job, company)
    assert res.score == 2 / 3  # Matched Python and React, missing Docker
    assert "Python" in res.matched
    assert "React" in res.matched
    assert "Docker" in res.missing

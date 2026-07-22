"""Unit tests for Technology, Experience, and Remote matchers."""

from __future__ import annotations

from datetime import datetime

from app.models import Company, JobPosting
from app.recommendation.profile import CandidateProfile
from app.recommendation.matching import TechnologyMatcher, ExperienceMatcher, RemoteMatcher


def test_technology_matcher():
    cand = CandidateProfile(technologies=["Go", "AWS", "MySQL"])
    job = JobPosting(job_title="Go Engineer", job_url="http://example.com/1", source="greenhouse")
    company = Company(
        name="Example",
        domain="example.com",
        description="We use AWS cloud systems.",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )

    res = TechnologyMatcher.match(cand, job, company)
    assert "Go" in res.matched
    assert "AWS" in res.matched
    assert "MySQL" in res.missing


def test_experience_matcher():
    # Senior title requires 5 years minimum
    job = JobPosting(job_title="Senior Python Architect", job_url="http://example.com/2", source="greenhouse")
    company = Company(name="Co", domain="co.com", discovered_at=datetime.utcnow(), last_updated=datetime.utcnow())

    # Candidate with 6 years experience -> Full score
    cand1 = CandidateProfile(years_experience=6.0)
    assert ExperienceMatcher.match(cand1, job, company).score == 1.0

    # Candidate with 2.5 years experience -> 0.5 score
    cand2 = CandidateProfile(years_experience=2.5)
    assert ExperienceMatcher.match(cand2, job, company).score == 0.5


def test_remote_matcher():
    job = JobPosting(job_title="Engineer", job_url="http://example.com/3", remote_type="hybrid", source="greenhouse")
    company = Company(name="Co", domain="co.com", discovered_at=datetime.utcnow(), last_updated=datetime.utcnow())

    cand_remote = CandidateProfile(remote_preference="remote")
    cand_hybrid = CandidateProfile(remote_preference="hybrid")

    assert RemoteMatcher.match(cand_remote, job, company).score == 0.5
    assert RemoteMatcher.match(cand_hybrid, job, company).score == 1.0

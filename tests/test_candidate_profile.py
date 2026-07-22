"""Unit tests for the CandidateProfile model."""

from __future__ import annotations

from app.recommendation.profile import CandidateProfile


def test_candidate_profile_defaults():
    cand = CandidateProfile()
    assert len(cand.skills) == 0
    assert len(cand.technologies) == 0
    assert cand.years_experience == 0.0
    assert cand.remote_preference == "any"
    assert cand.salary_expectation is None


def test_candidate_profile_custom_values():
    cand = CandidateProfile(
        skills=["Python", "System Design"],
        technologies=["AWS", "FastAPI"],
        years_experience=5.5,
        remote_preference="remote",
        salary_expectation=120000,
    )
    assert cand.skills == ["Python", "System Design"]
    assert cand.technologies == ["AWS", "FastAPI"]
    assert cand.years_experience == 5.5
    assert cand.remote_preference == "remote"
    assert cand.salary_expectation == 120000

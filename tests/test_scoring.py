"""Unit tests for the RecommendationScorer evaluating weighted score calculations."""

from __future__ import annotations

from datetime import datetime

from app.models import Company, JobPosting
from app.recommendation.profile import CandidateProfile
from app.recommendation.scoring import RecommendationScorer
from app.recommendation.weights import MatchWeights


def test_scorer_deterministic_math():
    cand = CandidateProfile(
        skills=["Python"],
        technologies=["AWS"],
        years_experience=5.0,
        remote_preference="remote",
    )
    job = JobPosting(
        job_title="Senior Developer",
        job_url="http://co.com/1",
        remote_type="remote",
        source="greenhouse",
    )
    company = Company(
        name="Co",
        domain="co.com",
        description="Python coding on AWS.",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
    )

    # All matchers (skills, technologies, experience, remote) should return 1.0 match scores.
    # Location defaults to 1.0 since candidate preferred_locations is empty.
    # Therefore final score should be exactly 100.0.
    score, results = RecommendationScorer.score_job(cand, job, company)
    assert score == 100.0

    # Custom weights
    custom_weights = MatchWeights(skills=0.8, technologies=0.2, experience=0.0, location=0.0, remote=0.0)
    score_custom, results_custom = RecommendationScorer.score_job(cand, job, company, weights=custom_weights)
    assert score_custom == 100.0

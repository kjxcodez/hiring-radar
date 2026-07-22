"""Unit tests for the RecommendationRanker matching ranking logic."""

from __future__ import annotations

from app.recommendation.ranking import RecommendationRanker


def test_ranking_logic():
    recs = [
        {"company_name": "Stripe", "job_title": "Engineer", "score": 85.2},
        {"company_name": "Google", "job_title": "Developer", "score": 92.5},
        {"company_name": "Apple", "job_title": "Designer", "score": 60.1},
    ]

    ranked = RecommendationRanker.rank(recs)

    assert ranked[0]["company_name"] == "Google"
    assert ranked[0]["rank"] == 1

    assert ranked[1]["company_name"] == "Stripe"
    assert ranked[1]["rank"] == 2

    assert ranked[2]["company_name"] == "Apple"
    assert ranked[2]["rank"] == 3

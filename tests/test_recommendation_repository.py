"""Unit tests for the RecommendationRepository persistent layer."""

from __future__ import annotations

from pathlib import Path

from app.storage import JsonStorage
from app.recommendation.repository import RecommendationRepository


def test_recommendation_repository_save_load_clear(tmp_path: Path):
    recs_file = tmp_path / "recommendations.json"
    repo = RecommendationRepository(recs_file, JsonStorage())

    # Starts empty
    assert repo.load_recommendations() == []

    # Save recommendations
    data = [
        {"company_name": "Google", "job_title": "Developer", "score": 95.0, "job_url": "http://google.com/1"},
        {"company_name": "Stripe", "job_title": "Engineer", "score": 88.0, "job_url": "http://stripe.com/1"},
    ]
    repo.save_recommendations(data)

    # Loads successfully
    loaded = repo.load_recommendations()
    assert len(loaded) == 2
    assert loaded[0]["company_name"] == "Google"

    # Find by job url
    found = repo.find_by_job_url("http://stripe.com/1")
    assert found is not None
    assert found["company_name"] == "Stripe"

    # Clear
    repo.clear()
    assert not recs_file.exists()
    assert repo.load_recommendations() == []

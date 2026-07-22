"""Unit tests for the Hiring trends analyzer."""

from __future__ import annotations

from app.models import JobPosting
from app.intelligence.hiring import HiringAnalyzer


def test_hiring_trends_analysis():
    jobs = [
        JobPosting(job_title="Senior Python Engineer", job_url="https://stripe.com/1", location="London", source="greenhouse"),
        JobPosting(job_title="Junior React Developer", job_url="https://stripe.com/2", location="Remote", source="greenhouse"),
        JobPosting(job_title="Product Manager", job_url="https://stripe.com/3", location="New York", source="greenhouse"),
        JobPosting(job_title="Lead Designer", job_url="https://stripe.com/4", location="New York", source="greenhouse"),
    ]

    res = HiringAnalyzer.analyze(jobs)
    assert res["open_roles"] == 4
    assert res["hiring_velocity"] == "stable"
    assert "Engineering" in res["departments"]
    assert "Product" in res["departments"]
    assert "Design" in res["departments"]
    
    assert res["seniority_distribution"]["Senior"] == 0.25
    assert res["seniority_distribution"]["Junior"] == 0.25
    assert res["seniority_distribution"]["Lead/Manager"] == 0.5
    assert res["seniority_distribution"]["Mid-level"] == 0.0

    
    assert "London" in res["geographic_distribution"]
    assert "Remote" in res["geographic_distribution"]
    assert "New York" in res["geographic_distribution"]

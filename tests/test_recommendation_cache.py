"""Unit tests for the RecommendationCache checksum invalidation."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.models import Company, JobPosting
from app.recommendation.profile import CandidateProfile
from app.recommendation.cache import RecommendationCache


def test_recommendation_cache_invalidation(tmp_path: Path):
    cand = CandidateProfile(skills=["Python"])
    job = JobPosting(job_title="Developer", job_url="http://co.com/1", source="greenhouse")
    company = Company(name="Co", domain="co.com", discovered_at=datetime.utcnow(), last_updated=datetime.utcnow())

    # 1. Base cache key
    key1 = RecommendationCache.calculate_cache_key(cand, company, job)

    # 2. Change candidate profile -> key changes
    cand_changed = CandidateProfile(skills=["Python", "FastAPI"])
    key2 = RecommendationCache.calculate_cache_key(cand_changed, company, job)
    assert key1 != key2

    # 3. Change job -> key changes
    job_changed = JobPosting(job_title="Lead Developer", job_url="http://co.com/1", source="greenhouse")
    key3 = RecommendationCache.calculate_cache_key(cand, company, job_changed)
    assert key1 != key3

    # 4. Introduce graph path -> key changes on graph contents modification
    graph_path = tmp_path / "knowledge_graph.json"
    graph_path.write_text('{"nodes": [], "edges": []}')
    key_graph1 = RecommendationCache.calculate_cache_key(cand, company, job, graph_path)

    graph_path.write_text('{"nodes": ["node1"], "edges": []}')
    key_graph2 = RecommendationCache.calculate_cache_key(cand, company, job, graph_path)
    assert key_graph1 != key_graph2

"""Unit tests for the Intelligence Cache manager."""

from __future__ import annotations

from datetime import datetime

from app.models import Company, JobPosting
from app.intelligence.profile import CompanyIntelligence
from app.intelligence.cache import IntelligenceCache


def test_intelligence_cache_validation():
    co = Company(
        name="Stripe",
        domain="stripe.com",
        discovered_at=datetime.utcnow(),
        last_updated=datetime.utcnow(),
        jobs=[
            JobPosting(
                job_title="Engineer",
                job_url="https://stripe.com/1",
                source="greenhouse",
            )
        ],
    )

    # 1. No intelligence profile -> not cached
    assert not IntelligenceCache.is_cached(co)

    # 2. Add intelligence profile and calculate cache key
    key1 = IntelligenceCache.calculate_cache_key(co)
    co.intelligence = CompanyIntelligence(cache_key=key1)

    assert IntelligenceCache.is_cached(co)

    # 3. Change jobs -> cache invalidated
    co.jobs.append(
        JobPosting(
            job_title="Designer",
            job_url="https://stripe.com/2",
            source="greenhouse",
        )
    )
    assert not IntelligenceCache.is_cached(co)

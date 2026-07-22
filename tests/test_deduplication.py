"""Tests for the Deduplicator — merge priority, cross-provider merging."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.discovery.deduplication import Deduplicator, _best_key
from app.models import Company, JobPosting


def _job(url: str = "https://example.com/job1", source: str = "test") -> JobPosting:
    return JobPosting(
        job_title="Engineer",
        job_url=url,
        source=source,
    )


def _co(
    name: str = "Acme Corp",
    *,
    ats_platform: str | None = None,
    ats_slug: str | None = None,
    domain: str | None = None,
    website: str | None = None,
    job_url: str = "https://example.com/job1",
) -> Company:
    now = datetime.now()
    return Company(
        name=name,
        ats_platform=ats_platform,
        ats_slug=ats_slug,
        domain=domain,
        website=website,
        jobs=[_job(url=job_url)],
        discovered_at=now,
        last_updated=now,
    )


class TestBestKey:

    def test_ats_key_priority(self):
        co = _co(ats_platform="greenhouse", ats_slug="acmecorp")
        assert _best_key(co) == "greenhouse::acmecorp"

    def test_domain_key_second_priority(self):
        co = _co(domain="acme.com")
        assert _best_key(co) == "acme.com"

    def test_website_key_third_priority(self):
        co = _co(website="https://www.acme.com")
        key = _best_key(co)
        assert "acme.com" in key

    def test_name_key_fallback(self):
        co = _co(name="Acme Corp")
        assert _best_key(co) == "acme corp"


class TestDeduplicator:

    def setup_method(self):
        self.dedup = Deduplicator()

    def test_new_company_added(self):
        incoming = [_co("NewCo", job_url="https://newco.com/job")]
        merged, new_count, updated_count = self.dedup.merge(incoming, [])
        assert new_count == 1
        assert updated_count == 0
        assert len(merged) == 1

    def test_existing_company_not_duplicated(self):
        co = _co("Acme", domain="acme.com", job_url="https://acme.com/job1")
        merged, new_count, updated_count = self.dedup.merge([co], [co])
        assert new_count == 0
        assert updated_count == 0
        assert len(merged) == 1

    def test_new_jobs_merged_into_existing(self):
        existing = _co("Acme", domain="acme.com", job_url="https://acme.com/job1")
        incoming = _co("Acme", domain="acme.com", job_url="https://acme.com/job2")
        merged, new_count, updated_count = self.dedup.merge([incoming], [existing])
        assert updated_count == 1
        assert len(merged) == 1
        assert len(merged[0].jobs) == 2

    def test_duplicate_jobs_not_re_added(self):
        """Same job URL must not be added twice."""
        existing = _co("Acme", domain="acme.com", job_url="https://acme.com/job1")
        incoming = _co("Acme", domain="acme.com", job_url="https://acme.com/job1")
        merged, _, updated = self.dedup.merge([incoming], [existing])
        assert len(merged[0].jobs) == 1  # No duplicate
        assert updated == 0  # Nothing new was added

    def test_ats_slug_priority_over_name(self):
        """Two records with same slug but different names → same company."""
        existing = _co("Acme", ats_platform="greenhouse", ats_slug="acmecorp", job_url="https://a.com/j1")
        incoming = _co("Acme Corporation", ats_platform="greenhouse", ats_slug="acmecorp", job_url="https://a.com/j2")
        merged, _, updated = self.dedup.merge([incoming], [existing])
        assert len(merged) == 1
        assert len(merged[0].jobs) == 2

    def test_dedupe_incoming_cross_provider(self):
        """Same company (same domain) from two providers → merged into one before repo merge."""
        co1 = _co("SharedCo", domain="shared.com", job_url="https://shared.com/j1")
        co2 = _co("SharedCo", domain="shared.com", job_url="https://shared.com/j2")
        result = self.dedup.dedupe_incoming([co1, co2])
        assert len(result) == 1
        assert len(result[0].jobs) == 2

    def test_multiple_different_companies(self):
        incoming = [
            _co("Alpha", job_url="https://alpha.com/j1"),
            _co("Beta", job_url="https://beta.com/j1"),
            _co("Gamma", job_url="https://gamma.com/j1"),
        ]
        merged, new_count, _ = self.dedup.merge(incoming, [])
        assert new_count == 3
        assert len(merged) == 3

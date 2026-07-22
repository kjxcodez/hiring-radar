"""Unit tests for the SyncMetrics model."""

from __future__ import annotations

from app.sync.metrics import SyncMetrics


def test_sync_metrics_initialization():
    m = SyncMetrics(provider="lever")
    assert m.provider == "lever"
    assert m.duration == 0.0
    assert m.companies_discovered == 0
    assert m.companies_updated == 0
    assert m.companies_removed == 0
    assert m.jobs_added == 0
    assert m.jobs_updated == 0
    assert m.jobs_removed == 0
    assert m.http_requests == 0
    assert m.skipped_requests == 0
    assert m.cache_hits == 0
    assert m.cache_misses == 0


def test_sync_metrics_updates():
    m = SyncMetrics(
        provider="lever",
        duration=5.2,
        companies_discovered=10,
        companies_updated=2,
        companies_removed=1,
        jobs_added=30,
        jobs_updated=5,
        jobs_removed=2,
        http_requests=8,
        skipped_requests=2,
        cache_hits=1,
        cache_misses=3,
    )
    assert m.duration == 5.2
    assert m.companies_discovered == 10
    assert m.companies_updated == 2
    assert m.companies_removed == 1
    assert m.jobs_added == 30
    assert m.jobs_updated == 5
    assert m.jobs_removed == 2
    assert m.http_requests == 8
    assert m.skipped_requests == 2
    assert m.cache_hits == 1
    assert m.cache_misses == 3

"""Unit tests for the MonitoringCache mapping fingerprint checks."""

from __future__ import annotations

from pathlib import Path
from app.storage import JsonStorage
from app.monitoring.cache import MonitoringCache


def test_monitoring_cache_checks(tmp_path: Path):
    cache_path = tmp_path / "monitoring_cache.json"
    cache = MonitoringCache(cache_path, JsonStorage())

    # Initially not unchanged -> registers hash and returns False
    assert not cache.is_unchanged("stripe.com", "hash1")

    # Second check with same hash -> returns True (unchanged)
    assert cache.is_unchanged("stripe.com", "hash1")

    # Third check with different hash -> returns False (changed) and updates
    assert not cache.is_unchanged("stripe.com", "hash2")
    assert cache.is_unchanged("stripe.com", "hash2")

    # Save and reload
    cache.save()
    cache2 = MonitoringCache(cache_path, JsonStorage())
    assert cache2.is_unchanged("stripe.com", "hash2")

    # Clear
    cache.clear()
    assert not cache_path.exists()

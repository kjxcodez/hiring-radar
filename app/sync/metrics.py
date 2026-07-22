"""Metrics model representing the performance and results of a sync operation."""

from __future__ import annotations

from pydantic import BaseModel


class SyncMetrics(BaseModel):
    """Synchronization statistics for monitoring and dashboards."""

    provider: str
    duration: float = 0.0
    companies_discovered: int = 0
    companies_updated: int = 0
    companies_removed: int = 0
    jobs_added: int = 0
    jobs_updated: int = 0
    jobs_removed: int = 0
    http_requests: int = 0
    skipped_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0

"""Self-invalidating cache manager for company intelligence data."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from app.sync.fingerprint import generate_company_fingerprint, generate_job_fingerprint

if TYPE_CHECKING:
    from app.models import Company


class IntelligenceCache:
    """Computes and validates cache keys for company enrichment."""

    @staticmethod
    def calculate_cache_key(company: Company) -> str:
        """Calculate a composite cache key from identity and jobs list.

        Combines:
        1. Company identity fingerprint
        2. Sorted jobs list fingerprints
        """
        # Identity fingerprint
        company_fp = generate_company_fingerprint(company)

        # Jobs fingerprint
        job_fps = [generate_job_fingerprint(j) for j in sorted(company.jobs, key=lambda x: x.job_url)]
        jobs_hash = hashlib.sha256("".join(job_fps).encode("utf-8")).hexdigest()

        # Combine all
        combined = f"{company_fp}:{jobs_hash}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    @staticmethod
    def is_cached(company: Company) -> bool:
        """Return True if the company's intelligence profile is current and cached."""
        if not company.intelligence or not company.intelligence.cache_key:
            return False

        current_key = IntelligenceCache.calculate_cache_key(company)
        return company.intelligence.cache_key == current_key

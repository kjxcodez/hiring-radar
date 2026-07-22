"""Self-invalidating cache manager for company intelligence data."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Optional

from app.sync.fingerprint import generate_company_fingerprint, generate_job_fingerprint

if TYPE_CHECKING:
    from app.models import Company


class IntelligenceCache:
    """Computes and validates cache keys for company enrichment."""

    @staticmethod
    def calculate_cache_key(
        company: Company,
        website_text: Optional[str] = None,
        github_text: Optional[str] = None,
    ) -> str:
        """Calculate a composite cache key from raw inputs.

        Combines:
        1. Company identity fingerprint
        2. Sorted jobs list fingerprints
        3. Website crawled content hash
        4. GitHub parsed content hash
        """
        # Identity fingerprint
        company_fp = generate_company_fingerprint(company)

        # Jobs fingerprint
        job_fps = [generate_job_fingerprint(j) for j in sorted(company.jobs, key=lambda x: x.job_url)]
        jobs_hash = hashlib.sha256("".join(job_fps).encode("utf-8")).hexdigest()

        # Web text hash
        web_hash = hashlib.sha256((website_text or "").encode("utf-8")).hexdigest()

        # GitHub text hash
        git_hash = hashlib.sha256((github_text or "").encode("utf-8")).hexdigest()

        # Combine all
        combined = f"{company_fp}:{jobs_hash}:{web_hash}:{git_hash}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

    @staticmethod
    def is_cached(
        company: Company,
        website_text: Optional[str] = None,
        github_text: Optional[str] = None,
    ) -> bool:
        """Return True if the company's intelligence profile is current and cached."""
        if not company.intelligence or not company.intelligence.cache_key:
            return False

        current_key = IntelligenceCache.calculate_cache_key(
            company, website_text=website_text, github_text=github_text
        )
        return company.intelligence.cache_key == current_key

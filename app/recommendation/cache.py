"""Cache key computation for candidate and job matches."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from app.sync.fingerprint import generate_company_fingerprint, generate_job_fingerprint

if TYPE_CHECKING:
    from app.models import Company, JobPosting
    from app.recommendation.profile import CandidateProfile


class RecommendationCache:
    """Computes and validates recommendation cache signatures."""

    @staticmethod
    def calculate_candidate_fingerprint(candidate: CandidateProfile) -> str:
        """Generate a stable fingerprint hash for the candidate profile."""
        profile_json = candidate.model_dump_json(warnings=False)
        return hashlib.sha256(profile_json.encode("utf-8")).hexdigest()

    @classmethod
    def calculate_cache_key(
        cls,
        candidate: CandidateProfile,
        company: Company,
        job: JobPosting,
        graph_path: Optional[Path] = None,
    ) -> str:
        """Calculate a composite cache key from candidate, company, job, and graph parameters."""
        cand_fp = cls.calculate_candidate_fingerprint(candidate)
        co_fp = generate_company_fingerprint(company)
        job_fp = generate_job_fingerprint(job)

        intel_fp = company.intelligence.cache_key if company.intelligence else ""

        # Graph checksum (from file modification or contents hash)
        graph_fp = ""
        if graph_path and graph_path.exists():
            try:
                # Read content and compute hash
                content = graph_path.read_bytes()
                graph_fp = hashlib.sha256(content).hexdigest()
            except Exception:
                pass

        combined = f"{cand_fp}:{co_fp}:{job_fp}:{intel_fp}:{graph_fp}"
        return hashlib.sha256(combined.encode("utf-8")).hexdigest()

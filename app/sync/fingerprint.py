"""Deterministic fingerprinting engine for companies and jobs."""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models import Company, JobPosting


def generate_company_fingerprint(company: Company) -> str:
    """Generate a deterministic SHA-256 hash representation of a Company.

    Uses domain, website, career_page_url, and name to create the signature.
    """
    data = {
        "domain": (company.domain or "").lower().strip(),
        "website": (company.website or "").lower().strip(),
        "career_page_url": (company.career_page_url or "").lower().strip(),
        "name": (company.name or "").lower().strip(),
    }
    dumped = json.dumps(data, sort_keys=True)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def generate_job_fingerprint(job: JobPosting) -> str:
    """Generate a deterministic SHA-256 hash representation of a JobPosting.

    Uses job_title, location, remote_type, and job_url to create the signature.
    """
    data = {
        "title": (job.job_title or "").lower().strip(),
        "location": (job.location or "").lower().strip(),
        "remote_type": (job.remote_type or "").lower().strip(),
        "url": (job.job_url or "").lower().strip(),
    }
    dumped = json.dumps(data, sort_keys=True)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()

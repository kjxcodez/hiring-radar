"""Snapshot model representing the exact state of a provider at a point in time."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.models import Company


class Snapshot(BaseModel):
    """Immutable snapshot of the data returned by a provider during a sync run."""

    provider: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    companies: List[Company] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    checksum: str = ""

    def calculate_checksum(self) -> str:
        """Compute SHA-256 checksum of normalized snapshot data.

        Normalizes and serializes the companies and their nested jobs to ensure
        deterministic hash generation across runs.
        """
        normalized_data = []
        # Sort companies by dedupe key to ensure order independence
        for co in sorted(self.companies, key=lambda c: c.dedupe_key()):
            co_dict = {
                "name": co.name,
                "domain": co.domain,
                "website": co.website,
                "career_page_url": co.career_page_url,
                "ats_platform": co.ats_platform,
                "ats_slug": co.ats_slug,
                "jobs": [
                    {
                        "job_title": j.job_title,
                        "job_url": j.job_url,
                        "location": j.location,
                        "remote_type": j.remote_type,
                    }
                    # Sort jobs by URL to ensure order independence
                    for j in sorted(co.jobs, key=lambda job: job.job_url)
                ],
            }
            normalized_data.append(co_dict)

        serialized = json.dumps(normalized_data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

"""Diff Engine for comparing snapshots and producing structured change lists."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field

from app.models import Company, JobPosting
from app.sync.fingerprint import generate_company_fingerprint, generate_job_fingerprint
from app.sync.snapshot import Snapshot


class SnapshotDiff(BaseModel):
    """Container for the structured differences between two snapshots."""

    added_companies: List[Company] = Field(default_factory=list)
    updated_companies: List[Company] = Field(default_factory=list)
    removed_companies: List[Company] = Field(default_factory=list)

    added_jobs: List[JobPosting] = Field(default_factory=list)
    updated_jobs: List[JobPosting] = Field(default_factory=list)
    removed_jobs: List[JobPosting] = Field(default_factory=list)

    unchanged_companies: List[Company] = Field(default_factory=list)
    unchanged_jobs: List[JobPosting] = Field(default_factory=list)


class DiffEngine:
    """Compares two provider snapshots to detect changes."""

    @staticmethod
    def diff(previous: Optional[Snapshot], current: Snapshot) -> SnapshotDiff:
        """Compare previous and current snapshots, classifying changes."""
        diff_result = SnapshotDiff()

        prev_cos = {c.dedupe_key(): c for c in previous.companies} if previous else {}
        curr_cos = {c.dedupe_key(): c for c in current.companies}

        # 1. Added companies
        for key, curr_co in curr_cos.items():
            if key not in prev_cos:
                diff_result.added_companies.append(curr_co)
                diff_result.added_jobs.extend(curr_co.jobs)

        # 2. Removed companies
        for key, prev_co in prev_cos.items():
            if key not in curr_cos:
                diff_result.removed_companies.append(prev_co)
                diff_result.removed_jobs.extend(prev_co.jobs)

        # 3. Intersecting companies (potentially updated or unchanged)
        for key in set(prev_cos.keys()).intersection(curr_cos.keys()):
            prev_co = prev_cos[key]
            curr_co = curr_cos[key]

            # Compare company-level fields (excluding jobs)
            prev_fp = generate_company_fingerprint(prev_co)
            curr_fp = generate_company_fingerprint(curr_co)

            prev_jobs = {j.job_url: j for j in prev_co.jobs}
            curr_jobs = {j.job_url: j for j in curr_co.jobs}

            co_jobs_added = []
            co_jobs_removed = []
            co_jobs_updated = []
            co_jobs_unchanged = []

            # Check job additions & updates
            for url, curr_job in curr_jobs.items():
                if url not in prev_jobs:
                    co_jobs_added.append(curr_job)
                else:
                    prev_job = prev_jobs[url]
                    if generate_job_fingerprint(prev_job) != generate_job_fingerprint(curr_job):
                        co_jobs_updated.append(curr_job)
                    else:
                        co_jobs_unchanged.append(curr_job)

            # Check job removals
            for url, prev_job in prev_jobs.items():
                if url not in curr_jobs:
                    co_jobs_removed.append(prev_job)

            # If company fields or jobs changed, it's an update
            if (
                prev_fp != curr_fp
                or co_jobs_added
                or co_jobs_removed
                or co_jobs_updated
            ):
                diff_result.updated_companies.append(curr_co)
                diff_result.added_jobs.extend(co_jobs_added)
                diff_result.updated_jobs.extend(co_jobs_updated)
                diff_result.removed_jobs.extend(co_jobs_removed)
            else:
                diff_result.unchanged_companies.append(curr_co)
                diff_result.unchanged_jobs.extend(co_jobs_unchanged)

        return diff_result

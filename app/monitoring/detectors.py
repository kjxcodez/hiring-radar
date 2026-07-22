"""Change detectors evaluating snapshot state adjustments."""

from __future__ import annotations

from typing import List, Dict, Any, Optional

from app.models import Company, JobPosting, Application
from app.monitoring.events import (
    ChangeEvent,
    JobCreated,
    JobClosed,
    JobUpdated,
    SalaryChanged,
    LocationChanged,
    RemotePolicyChanged,
    HiringStatusChanged,
    EngineeringStackChanged,
    RecruiterChanged,
    RecommendationChanged,
    ApplicationStatusChanged,
)
from app.monitoring.diff import CRMDiffEngine


class JobChangeDetector:
    """Detects changes in company job openings lists."""

    @staticmethod
    def detect(
        company_name: str,
        previous_jobs: List[JobPosting],
        current_jobs: List[JobPosting],
    ) -> List[ChangeEvent]:
        events = []
        prev_map = {j.job_url: j for j in previous_jobs} if previous_jobs else {}
        curr_map = {j.job_url: j for j in current_jobs}

        # 1. Job additions
        for url, curr_job in curr_map.items():
            if url not in prev_map:
                events.append(
                    JobCreated(
                        company_name=company_name,
                        job_url=url,
                        current_value=curr_job.job_title,
                        metadata={"title": curr_job.job_title},
                    )
                )
            else:
                # 2. Job updates
                prev_job = prev_map[url]

                # Check remote changes
                if prev_job.remote_type != curr_job.remote_type:
                    events.append(
                        RemotePolicyChanged(
                            company_name=company_name,
                            job_url=url,
                            previous_value=prev_job.remote_type,
                            current_value=curr_job.remote_type,
                        )
                    )
                # Check location changes
                if prev_job.location != curr_job.location:
                    events.append(
                        LocationChanged(
                            company_name=company_name,
                            job_url=url,
                            previous_value=prev_job.location,
                            current_value=curr_job.location,
                        )
                    )

        # 3. Job removals
        for url, prev_job in prev_map.items():
            if url not in curr_map:
                events.append(
                    JobClosed(
                        company_name=company_name,
                        job_url=url,
                        previous_value=prev_job.job_title,
                        metadata={"title": prev_job.job_title},
                    )
                )

        return events


class CompanyChangeDetector:
    """Detects company properties modifications."""

    @staticmethod
    def detect(previous: Company, current: Company) -> List[ChangeEvent]:
        events = []
        if previous.company_score_overall != current.company_score_overall:
            events.append(
                HiringStatusChanged(
                    company_name=current.name,
                    previous_value=str(previous.company_score_overall),
                    current_value=str(current.company_score_overall),
                )
            )
        return events


class IntelligenceChangeDetector:
    """Detects company intelligence signals adjustments."""

    @staticmethod
    def detect(company_name: str, previous: Optional[Dict[str, Any]], current: Optional[Dict[str, Any]]) -> List[ChangeEvent]:
        events = []
        if not previous or not current:
            return events

        # Compare engineering stack changes
        old_stack = previous.get("tech_stack", [])
        new_stack = current.get("tech_stack", [])
        if set(old_stack) != set(new_stack):
            events.append(
                EngineeringStackChanged(
                    company_name=company_name,
                    previous_value=", ".join(old_stack),
                    current_value=", ".join(new_stack),
                )
            )

        # Compare recruiter changes
        old_rec = previous.get("recruiters", [])
        new_rec = current.get("recruiters", [])
        if len(old_rec) != len(new_rec):
            events.append(
                RecruiterChanged(
                    company_name=company_name,
                    previous_value=f"{len(old_rec)} recruiters",
                    current_value=f"{len(new_rec)} recruiters",
                )
            )

        return events


class RecommendationChangeDetector:
    """Detects shifts in match scores or rankings."""

    @staticmethod
    def detect(previous: List[dict], current: List[dict]) -> List[ChangeEvent]:
        events = []
        prev_map = {r.get("job_url"): r for r in previous if r.get("job_url")} if previous else {}
        curr_map = {r.get("job_url"): r for r in current if r.get("job_url")}

        for url, curr_rec in curr_map.items():
            co_name = curr_rec.get("company_name", "Unknown")
            if url in prev_map:
                prev_rec = prev_map[url]
                old_score = prev_rec.get("score", 0.0)
                new_score = curr_rec.get("score", 0.0)
                if abs(old_score - new_score) > 0.01:
                    events.append(
                        RecommendationChanged(
                            company_name=co_name,
                            job_url=url,
                            previous_value=f"{old_score:.1f}%",
                            current_value=f"{new_score:.1f}%",
                            metadata={"type": "score_shift"},
                        )
                    )
        return events


class ApplicationChangeDetector:
    """Detects CRM tracking phase transitions."""

    @staticmethod
    def detect(previous: Dict[str, Application], current: Dict[str, Application]) -> List[ChangeEvent]:
        events = []
        for key, curr_app in current.items():
            co_name = curr_app.company.name if curr_app.company else key
            if key in previous:
                prev_app = previous[key]
                if prev_app.status != curr_app.status:
                    events.append(
                        ApplicationStatusChanged(
                            company_name=co_name,
                            previous_value=prev_app.status,
                            current_value=curr_app.status,
                        )
                    )
        return events

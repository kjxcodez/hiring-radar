"""Generic post-discovery filtering engine for hiring-radar.

Filters companies and job postings based on search profiles and individual CLI constraints.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

from app.models import Company

if TYPE_CHECKING:
    from app.profiles import SearchProfile


def apply_filters(
    companies: list[Company],
    profile: SearchProfile | None = None,
    remote: bool | None = None,
    country: str | None = None,
    keyword: str | None = None,
    exclude: str | None = None,
    days: int | None = None,
) -> list[Company]:
    """Filter jobs within each company, returning a new list of modified Company objects.

    Companies left with zero matching jobs are omitted from the output.

    Filters layer on top of each other (AND logic between different axes;
    OR logic within list fields like profile keywords/countries).

    Docstring examples / expected behavior:
    1. Filter by Remote:
       - remote=True keeps only jobs with remote_type == "remote".
       - remote=False keeps only jobs with remote_type != "remote".
    2. Filter by Keywords (case-insensitive):
       - If profile has keywords ['react', 'vue'], job_title must contain either.
       - If CLI keyword is 'senior', job_title must also contain 'senior'.
    3. Filter by Exclude (case-insensitive):
       - If job_title contains any exclude term, the job is dropped.
    4. Filter by Country:
       - Job location must contain the country name.
    5. Filter by Days:
       - Jobs posted older than N days ago are dropped (jobs with posted_date=None are kept).

    Args:
        companies: List of Company objects to filter.
        profile: A SearchProfile containing criteria.
        remote: CLI flag override for remote jobs.
        country: CLI flag constraint for target country.
        keyword: CLI flag constraint for target job title keyword.
        exclude: CLI flag constraint for terms to exclude from job titles.
        days: CLI flag constraint for maximum age of postings in days.

    Returns:
        A new list of filtered Company copies.
    """
    # 1. Resolve constraints on each axis
    # Remote constraint
    remote_target = remote
    if remote_target is None and profile is not None:
        remote_target = profile.remote

    # Keyword constraints
    profile_keywords = profile.keywords if profile else []
    cli_keyword = keyword.strip() if keyword else None

    # Exclude constraints
    profile_excludes = profile.exclude if profile else []
    cli_exclude = exclude.strip() if exclude else None

    # Country constraints
    profile_countries = profile.countries if profile else []
    cli_country = country.strip() if country else None

    # Date constraint
    cutoff_date = None
    if days is not None:
        cutoff_date = date.today() - timedelta(days=days)

    filtered_companies: list[Company] = []

    for company in companies:
        matching_jobs = []

        for job in company.jobs:
            # Remote check
            if remote_target is not None:
                is_job_remote = job.remote_type == "remote"
                if remote_target != is_job_remote:
                    continue

            # Profile keywords check (OR logic: match at least one if list is not empty)
            if profile_keywords:
                title_lower = job.job_title.lower()
                if not any(k.lower() in title_lower for k in profile_keywords):
                    continue

            # CLI keyword check (AND constraint on top of profile)
            if cli_keyword:
                if cli_keyword.lower() not in job.job_title.lower():
                    continue

            # Profile excludes check (AND constraint: must not match any)
            if profile_excludes:
                title_lower = job.job_title.lower()
                if any(ex.lower() in title_lower for ex in profile_excludes):
                    continue

            # CLI exclude check (AND constraint)
            if cli_exclude:
                if cli_exclude.lower() in job.job_title.lower():
                    continue

            # Profile countries check (OR logic: location must contain at least one country)
            if profile_countries:
                loc = (job.location or "").lower()
                if not any(c.lower() in loc for c in profile_countries):
                    continue

            # CLI country check (AND constraint)
            if cli_country:
                loc = (job.location or "").lower()
                if cli_country.lower() not in loc:
                    continue

            # Age check (exclude only if we have posted_date AND it is older than cutoff_date)
            if cutoff_date and job.posted_date:
                if job.posted_date < cutoff_date:
                    continue

            # All checks passed!
            matching_jobs.append(job)

        if matching_jobs:
            # Create a non-mutating copy of the company with the updated jobs list
            filtered_companies.append(
                company.model_copy(update={"jobs": matching_jobs})
            )

    return filtered_companies

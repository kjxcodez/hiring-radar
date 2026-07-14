"""CSV export module for hiring-radar.

This module intentionally avoids dependencies like pandas because the standard library's
`csv.DictWriter` is extremely efficient, highly portable, and sufficient at this scale.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Literal

from app.models import Company


def export_csv(
    companies: list[Company],
    output_path: Path,
    granularity: Literal["company", "job"] = "company",
) -> None:
    """Export a list of companies (and optionally their jobs) to a CSV file.

    Rows are sorted alphabetically by company name.

    Args:
        companies: List of Company objects to export.
        output_path: Destination path for the CSV.
        granularity: "company" to output one row per company, or "job" to output one
            row per job posting with company metadata repeated.
    """
    # Sort companies alphabetically by name
    sorted_companies = sorted(companies, key=lambda c: c.name.lower())

    # Build directory if it doesn't exist
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Base company fields common to both granularities
    company_fieldnames = [
        "name",
        "domain",
        "website",
        "career_page_url",
        "ats_platform",
        "industry",
        "description",
        "company_size",
        "founded_year",
        "linkedin_url",
        "github_url",
        "social_links",
        "generic_emails",
        "recruiter_name",
        "recruiter_email",
        "recruiter_linkedin",
        "job_count",
        "job_titles",
        "ai_summary",
        "notes",
    ]

    if granularity == "company":
        fieldnames = company_fieldnames
    else:
        # granularity == "job"
        fieldnames = company_fieldnames + [
            "job_title",
            "job_url",
            "location",
            "remote_type",
            "job_source",
            "posted_date",
        ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for company in sorted_companies:
            # Prepare company metadata dictionary
            desc = company.description or ""
            if len(desc) > 300:  # noqa: PLR2004
                desc = desc[:297] + "..."

            # First 5 jobs titles for company granularity
            job_titles_preview = "; ".join(j.job_title for j in company.jobs[:5])

            company_data = {
                "name": company.name,
                "domain": company.domain or "",
                "website": company.website or "",
                "career_page_url": company.career_page_url or "",
                "ats_platform": company.ats_platform or "",
                "industry": company.industry or "",
                "description": desc,
                "company_size": company.company_size or "",
                "founded_year": str(company.founded_year) if company.founded_year else "",
                "linkedin_url": company.linkedin_url or "",
                "github_url": company.github_url or "",
                "social_links": "; ".join(company.social_links),
                "generic_emails": "; ".join(company.generic_emails),
                "recruiter_name": company.recruiter_name or "",
                "recruiter_email": company.recruiter_email or "",
                "recruiter_linkedin": company.recruiter_linkedin or "",
                "job_count": len(company.jobs),
                "job_titles": job_titles_preview,
                "ai_summary": company.ai_summary or "",
                "notes": "; ".join(company.notes),
            }

            if granularity == "company":
                writer.writerow(company_data)
            else:
                # If there are no jobs, write one row with empty job fields
                if not company.jobs:
                    job_data = {
                        "job_title": "",
                        "job_url": "",
                        "location": "",
                        "remote_type": "",
                        "job_source": "",
                        "posted_date": "",
                    }
                    row = {**company_data, **job_data}
                    writer.writerow(row)
                else:
                    for job in company.jobs:
                        job_data = {
                            "job_title": job.job_title,
                            "job_url": job.job_url,
                            "location": job.location or "",
                            "remote_type": job.remote_type,
                            "job_source": job.source,
                            "posted_date": job.posted_date.isoformat() if job.posted_date else "",
                        }
                        row = {**company_data, **job_data}
                        writer.writerow(row)

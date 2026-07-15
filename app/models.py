"""Pydantic v2 data models for hiring-radar.

No I/O, HTTP, or file logic lives here — pure data shapes only.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class JobPosting(BaseModel):
    """A single open role scraped from an ATS or job board."""

    model_config = ConfigDict(str_strip_whitespace=True)

    job_title: str
    job_url: str
    location: str | None = None
    remote_type: Literal["remote", "hybrid", "onsite", "unknown"] = "unknown"
    source: str  # e.g. "greenhouse", "lever", "remoteok", "wwr"
    posted_date: date | None = None


class Company(BaseModel):
    """A company discovered to be actively hiring, with enrichment data attached.

    Aggregates one or more JobPosting records together with contact hints,
    AI-generated outreach material, and scrape metadata.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    # --- Identity ---
    name: str
    domain: str | None = None
    website: str | None = None
    career_page_url: str | None = None

    # --- ATS metadata (set by discover stage) ---
    ats_platform: str | None = None   # "greenhouse" | "lever" | "ashby" | etc.
    ats_slug: str | None = None       # company slug/id on that ATS, for re-fetching

    # --- Firmographic enrichment ---
    industry: str | None = None
    description: str | None = None
    company_size: str | None = None
    founded_year: int | None = None

    # --- Social / contact ---
    linkedin_url: str | None = None
    github_url: str | None = None
    social_links: list[str] = Field(default_factory=list)
    generic_emails: list[str] = Field(default_factory=list)

    # --- Recruiter contact ---
    recruiter_name: str | None = None
    recruiter_email: str | None = None
    recruiter_linkedin: str | None = None

    # --- Operational metadata ---
    notes: list[str] = Field(default_factory=list)
    """Append-only log of scrape/enrich events, e.g. 'scrape_failed: timeout'."""

    # --- Jobs ---
    jobs: list[JobPosting] = Field(default_factory=list)

    # --- AI-generated outreach material ---
    ai_summary: str | None = None
    ai_talking_points: list[str] = Field(default_factory=list)
    ai_fit_rationale: str | None = None
    research_notes: dict[str, str] = Field(default_factory=dict)
    company_scores: dict[str, int] = Field(default_factory=dict)
    company_score_overall: float | None = None



    # --- Timestamps ---
    discovered_at: datetime
    last_updated: datetime

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def dedupe_key(self) -> str:
        """Return a stable, normalised string used to deduplicate Company records.

        Prefers the domain (most stable identifier); falls back to the company
        name when domain is absent.  Both are lowercased and stripped so that
        records from different sources can be merged reliably.
        """
        if self.domain:
            return self.domain.lower().strip()
        return self.name.lower().strip()


ApplicationStatus = Literal["discovered", "researched", "applied", "interviewing", "rejected", "offer"]


class Application(BaseModel):
    """An tracking record for a job application process with a specific company."""

    model_config = ConfigDict(str_strip_whitespace=True)

    company_key: str          # Company.dedupe_key()
    status: ApplicationStatus = "discovered"
    status_history: list[dict] = Field(default_factory=list)   # [{"status": ..., "date": iso string}, ...]
    applied_date: date | None = None
    resume_version: str | None = None
    notes: list[str] = Field(default_factory=list)
    last_contact_date: date | None = None


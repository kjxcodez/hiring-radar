"""Pydantic v2 data models for hiring-radar.

No I/O, HTTP, or file logic lives here — pure data shapes only.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Dict, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

class CandidateProfile(BaseModel):
    """Structured candidate profile representing skills, preferences, and experience."""

    skills: List[str] = Field(default_factory=list)
    technologies: List[str] = Field(default_factory=list)
    years_experience: float = 0.0
    preferred_roles: List[str] = Field(default_factory=list)
    preferred_locations: List[str] = Field(default_factory=list)
    remote_preference: str = "any"  # "remote", "hybrid", "onsite", "any"
    salary_expectation: Optional[int] = None  # Minimum annual salary expected (USD)
    seniority: str = "mid"  # "junior", "mid", "senior", "lead"
    education: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    career_goals: List[str] = Field(default_factory=list)


class BusinessProfile(BaseModel):
    """Firmographic and operational business details."""
    industry: Optional[str] = None
    category: Optional[str] = None
    company_size: Optional[str] = None
    headquarters: Optional[str] = None
    remote_policy: Optional[str] = None
    founded_year: Optional[int] = None

class EngineeringProfile(BaseModel):
    """Technology stack details inferred from jobs and code repositories."""
    languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    infrastructure: List[str] = Field(default_factory=list)
    cloud: List[str] = Field(default_factory=list)
    databases: List[str] = Field(default_factory=list)
    ci_cd: List[str] = Field(default_factory=list)
    ai_stack: List[str] = Field(default_factory=list)

class HiringProfile(BaseModel):
    """Hiring velocity and department trends analysis."""
    hiring_velocity: str = "stable"  # "growing", "stable", "declining"
    open_roles: int = 0
    departments: List[str] = Field(default_factory=list)
    seniority_distribution: Dict[str, float] = Field(default_factory=dict)
    geographic_distribution: List[str] = Field(default_factory=list)

class GitHubProfile(BaseModel):
    """Open-source intelligence from corporate repositories."""
    organization: Optional[str] = None
    popular_repositories: List[str] = Field(default_factory=list)
    stars: int = 0
    activity: str = "medium"  # "high", "medium", "low"
    languages: List[str] = Field(default_factory=list)
    contributors: int = 0

class SignalsProfile(BaseModel):
    """Detected business growth and engineering culture signals."""
    funding_stage: Optional[str] = None
    startup_maturity: str = "mid"  # "early", "mid", "late", "enterprise"
    enterprise_score: float = 0.0
    engineering_culture: List[str] = Field(default_factory=list)
    oss_friendliness: float = 0.0
    ai_adoption: float = 0.0

class CompanyIntelligence(BaseModel):
    """Complete company intelligence profile aggregating all sub-profiles."""
    business: BusinessProfile = Field(default_factory=BusinessProfile)
    engineering: EngineeringProfile = Field(default_factory=EngineeringProfile)
    hiring: HiringProfile = Field(default_factory=HiringProfile)
    github: GitHubProfile = Field(default_factory=GitHubProfile)
    signals: SignalsProfile = Field(default_factory=SignalsProfile)
    cache_key: Optional[str] = None






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
    intelligence: Optional[CompanyIntelligence] = None

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


class OutreachMessage(BaseModel):
    """An outreach message draft or sent log."""

    channel: str  # "email", "linkedin", "referral"
    subject: Optional[str] = None
    content: str
    generated_at: str
    user_approved: bool = False
    sent_at: Optional[str] = None


class Recruiter(BaseModel):
    """Corporate recruiter contact details."""

    name: Optional[str] = None
    email: Optional[str] = None
    linkedin: Optional[str] = None
    role: Optional[str] = None


class Referral(BaseModel):
    """Referral details for employee introductions."""

    name: Optional[str] = None
    connection: Optional[str] = None  # e.g. "Alumni", "Mutual connection"
    email: Optional[str] = None
    status: str = "pending"  # "pending", "contacted", "referred", "none"


class FollowUp(BaseModel):
    """A scheduled follow-up reminder event."""

    day: int  # Offset days from apply date
    action: str  # e.g. "Send email follow-up"
    template_name: str
    status: str = "pending"  # "pending", "completed", "skipped"


class TimelineEntry(BaseModel):
    """An event on the application timeline."""

    event: str  # e.g. "Applied", "Technical Interview Scheduled"
    description: str
    timestamp: str
    metadata: Dict[str, str] = Field(default_factory=dict)


ApplicationStatus = Literal[
    "discovered", "researched", "applied", "interviewing", "rejected", "offer",
    "Planned", "Prepared", "Applied", "Recruiter Contacted", "Screening",
    "Technical Interview", "Manager Interview", "Offer", "Accepted", "Rejected", "Withdrawn"
]



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

    # Outreach CRM fields
    candidate: Optional[CandidateProfile] = None
    company: Optional[Company] = None
    job: Optional[JobPosting] = None
    recruiter: Optional[Recruiter] = None
    referral: Optional[Referral] = None
    cover_letter_version: str | None = None
    messages: list[OutreachMessage] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    next_followup: Optional[str] = None
    followup_schedule: list[FollowUp] = Field(default_factory=list)
    last_updated: Optional[datetime] = None



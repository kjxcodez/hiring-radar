"""Company Intelligence Profile Pydantic schemas."""

from __future__ import annotations

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


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

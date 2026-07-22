"""Candidate profile data models for job recommendation matching."""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, Field


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

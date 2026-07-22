"""Configurable weighting profiles for recommendation scoring."""

from __future__ import annotations

from pydantic import BaseModel, Field


class MatchWeights(BaseModel):
    """Configurable weights totaling to 1.0 (or normalized during scoring)."""

    skills: float = Field(default=0.30, description="Weight of candidate skills keyword matches.")
    technologies: float = Field(default=0.25, description="Weight of candidate technology stack overlap.")
    experience: float = Field(default=0.15, description="Weight of candidate years of experience vs job requirements.")
    location: float = Field(default=0.15, description="Weight of candidate preferred location matches.")
    remote: float = Field(default=0.15, description="Weight of candidate remote/hybrid/onsite preferences.")


DEFAULT_WEIGHTS = MatchWeights()

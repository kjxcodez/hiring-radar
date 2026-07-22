"""Re-exports CandidateProfile from app.models to prevent circular imports."""

from __future__ import annotations

from app.models import CandidateProfile

__all__ = ["CandidateProfile"]

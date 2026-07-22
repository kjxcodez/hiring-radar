"""Scoring engine computing deterministic suitability ratings."""

from __future__ import annotations

from typing import Dict, Tuple

from app.models import Company, JobPosting
from app.recommendation.profile import CandidateProfile
from app.recommendation.matching import (
    SkillMatcher,
    TechnologyMatcher,
    ExperienceMatcher,
    LocationMatcher,
    RemoteMatcher,
    MatchResult,
)
from app.recommendation.weights import DEFAULT_WEIGHTS, MatchWeights


class RecommendationScorer:
    """Computes a composite, deterministic match score between a candidate and a job opening."""

    @staticmethod
    def score_job(
        candidate: CandidateProfile,
        job: JobPosting,
        company: Company,
        weights: MatchWeights = DEFAULT_WEIGHTS,
    ) -> Tuple[float, Dict[str, MatchResult]]:
        """Score a single job posting deterministically.

        Returns:
            A tuple of (final_score, component_match_results).
            final_score is between 0.0 and 100.0.
        """
        results: Dict[str, MatchResult] = {
            "skills": SkillMatcher.match(candidate, job, company),
            "technologies": TechnologyMatcher.match(candidate, job, company),
            "experience": ExperienceMatcher.match(candidate, job, company),
            "location": LocationMatcher.match(candidate, job, company),
            "remote": RemoteMatcher.match(candidate, job, company),
        }

        # Calculate weighted sum
        total_weight = (
            weights.skills
            + weights.technologies
            + weights.experience
            + weights.location
            + weights.remote
        )

        weighted_sum = (
            (results["skills"].score * weights.skills)
            + (results["technologies"].score * weights.technologies)
            + (results["experience"].score * weights.experience)
            + (results["location"].score * weights.location)
            + (results["remote"].score * weights.remote)
        )

        final_score = round((weighted_sum / total_weight) * 100.0, 1) if total_weight > 0 else 0.0
        return final_score, results

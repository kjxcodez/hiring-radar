"""Job recommendation engine package.

Includes candidate profile builders, resume parsers, deterministic matchers,
weights configuration, AI match explanations, and persistence repositories.
"""

from __future__ import annotations

from app.recommendation.profile import CandidateProfile
from app.recommendation.resume import ResumeParser
from app.recommendation.weights import MatchWeights, DEFAULT_WEIGHTS
from app.recommendation.matching import (
    MatchResult,
    SkillMatcher,
    TechnologyMatcher,
    ExperienceMatcher,
    LocationMatcher,
    RemoteMatcher,
)
from app.recommendation.scoring import RecommendationScorer
from app.recommendation.ranking import RecommendationRanker
from app.recommendation.explanations import AIExplainer
from app.recommendation.cache import RecommendationCache
from app.recommendation.repository import RecommendationRepository
from app.recommendation.engine import RecommendationEngine

__all__ = [
    "CandidateProfile",
    "ResumeParser",
    "MatchWeights",
    "DEFAULT_WEIGHTS",
    "MatchResult",
    "SkillMatcher",
    "TechnologyMatcher",
    "ExperienceMatcher",
    "LocationMatcher",
    "RemoteMatcher",
    "RecommendationScorer",
    "RecommendationRanker",
    "AIExplainer",
    "RecommendationCache",
    "RecommendationRepository",
    "RecommendationEngine",
]

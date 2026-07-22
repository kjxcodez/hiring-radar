"""Ranking engine sorting matched roles by suitability."""

from __future__ import annotations

from typing import Any, Dict, List


class RecommendationRanker:
    """Sorts and ranks calculated job recommendation tuples."""

    @staticmethod
    def rank(recommendations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort list of recommendation dicts by score descending, adding rank index.

        Args:
            recommendations: List of dicts, each having key "score".
        """
        # Sort by score descending
        sorted_recs = sorted(recommendations, key=lambda x: x.get("score", 0.0), reverse=True)

        # Assign rank index (1-based)
        for idx, rec in enumerate(sorted_recs):
            rec["rank"] = idx + 1

        return sorted_recs

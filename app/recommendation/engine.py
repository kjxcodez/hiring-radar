"""Orchestration engine coordinating scoring, ranking, AI explanations, and caching."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, TYPE_CHECKING

from loguru import logger

from app.recommendation.profile import CandidateProfile
from app.recommendation.scoring import RecommendationScorer
from app.recommendation.ranking import RecommendationRanker
from app.recommendation.explanations import AIExplainer
from app.recommendation.cache import RecommendationCache

if TYPE_CHECKING:
    from app.services.config import ServiceContainer


class RecommendationEngine:
    """Core recommendation workflow coordinator."""

    def __init__(self, container: ServiceContainer, settings: Any) -> None:
        self.container = container
        self.settings = settings
        self.ai_gateway = container.ai_gateway
        self.company_repo = container.company_repo
        
        # Repository for recommendations
        recs_filepath = self.settings.output_dir / "recommendations.json"
        from app.recommendation.repository import RecommendationRepository
        self.rec_repo = RecommendationRepository(recs_filepath, self.company_repo.storage)

    def recommend(self, candidate: CandidateProfile, force: bool = False) -> List[Dict[str, Any]]:
        """Run candidate-job matching pipeline, score, rank, explain, and persist results."""
        logger.info("recommendation: starting match engine pipeline...")

        companies = self.company_repo.load_all()
        if not companies:
            logger.info("recommendation: no companies found, clearing recommendations.")
            self.rec_repo.clear()
            return []

        # Load existing recommendations for caching checks
        existing_recs = self.rec_repo.load_recommendations()
        existing_recs_map = {r.get("job_url"): r for r in existing_recs if r.get("job_url")}

        graph_path = self.settings.output_dir / "knowledge_graph.json"

        processed_recs: List[Dict[str, Any]] = []

        for company in companies:
            for job in company.jobs:
                if not job.job_url:
                    continue

                # 1. Compute composite cache key
                cache_key = RecommendationCache.calculate_cache_key(
                    candidate, company, job, graph_path
                )

                # 2. Check Cache
                cached_rec = existing_recs_map.get(job.job_url)
                if cached_rec and cached_rec.get("cache_key") == cache_key and not force:
                    # Keep cached item
                    processed_recs.append(cached_rec)
                    continue

                # 3. Cache Miss: Recalculate Score
                score, match_results = RecommendationScorer.score_job(candidate, job, company)

                # 4. Generate AI Explanations
                ai_res = AIExplainer.explain(
                    candidate, job, company, match_results, self.ai_gateway
                )

                # 5. Assemble recommendation entry
                entry = {
                    "company_name": company.name,
                    "job_title": job.job_title,
                    "job_url": job.job_url,
                    "score": score,
                    "cache_key": cache_key,
                    "explanation": ai_res,
                    "missing_skills": match_results["skills"].missing,
                    "strengths": ai_res.get("strengths") or match_results["skills"].matched,
                    "weaknesses": ai_res.get("weaknesses") or match_results["skills"].missing,
                    "generated_at": datetime.now().isoformat(),
                }
                processed_recs.append(entry)

        # 6. Rank all matches
        ranked_recs = RecommendationRanker.rank(processed_recs)

        # 7. Persist results
        self.rec_repo.save_recommendations(ranked_recs)
        logger.info("recommendation: match pipeline complete. Saved {n} jobs.", n=len(ranked_recs))

        return ranked_recs

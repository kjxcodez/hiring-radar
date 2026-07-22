"""AI explainer compiling personalized matching context and preparation roadmaps."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Dict, List, Optional

from loguru import logger

if TYPE_CHECKING:
    from app.ai.gateway import AiGateway
    from app.models import Company, JobPosting
    from app.recommendation.profile import CandidateProfile
    from app.recommendation.matching import MatchResult


_SAFE_EXPLANATION = {
    "why_fit": "This role is a partial match based on candidate profile skills.",
    "strengths": [],
    "weaknesses": [],
    "missing_skills_analysis": "Some skill requirements may not be explicitly listed in the profile.",
    "resume_improvements": [],
    "interview_prep_tips": [],
    "study_roadmap": [],
    "outreach_talking_points": [],
}


class AIExplainer:
    """Generates LLM explanations for job recommendations."""

    @staticmethod
    def explain(
        candidate: CandidateProfile,
        job: JobPosting,
        company: Company,
        match_results: Dict[str, MatchResult],
        gateway: AiGateway,
    ) -> Dict[str, any]:
        """Explain recommendation alignment via LLM."""
        # Compile contextual parameters
        context = {
            "candidate": {
                "skills": candidate.skills,
                "technologies": candidate.technologies,
                "experience": candidate.years_experience,
                "preferred_roles": candidate.preferred_roles,
                "preferred_locations": candidate.preferred_locations,
                "remote_preference": candidate.remote_preference,
            },
            "job": {
                "title": job.job_title,
                "location": job.location,
                "remote_type": job.remote_type,
            },
            "company": {
                "name": company.name,
                "description": company.description,
            },
            "match_details": {
                k: {"score": v.score, "matched": v.matched, "missing": v.missing, "reason": v.reason}
                for k, v in match_results.items()
            },
        }

        user_content = json.dumps(context, indent=2)

        try:
            raw_response = gateway.complete(
                prompt_id="recommend_explain.v1",
                user_content=user_content,
                temperature=0.3,
                use_cache=True,
            )

            if not raw_response:
                return _SAFE_EXPLANATION

            # Strip markdown code fences if present
            from app.ai import clean_json_content
            cleaned = clean_json_content(raw_response)

            parsed = json.loads(cleaned)
            # Ensure all required keys exist
            for k, default_val in _SAFE_EXPLANATION.items():
                if k not in parsed:
                    parsed[k] = default_val
            return parsed

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "explainer: AI explanation generation failed for '{j}' at '{c}' — {exc}",
                j=job.job_title,
                c=company.name,
                exc=exc,
            )
            return _SAFE_EXPLANATION

"""Referral request generator drafting mutual connection outreach notes."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from app.ai.gateway import AiGateway
    from app.models import Company, JobPosting
    from app.recommendation.profile import CandidateProfile


class ReferralRequestGenerator:
    """Generates employee referral request notes."""

    @staticmethod
    def generate(
        candidate: CandidateProfile,
        job: JobPosting,
        company: Company,
        gateway: AiGateway,
    ) -> Dict[str, str]:
        """Call AI Gateway to draft referral request message."""
        context = {
            "candidate": {
                "skills": candidate.skills,
                "experience": candidate.years_experience,
            },
            "job": {
                "title": job.job_title,
            },
            "company": {
                "name": company.name,
            },
        }

        user_content = json.dumps(context, indent=2)

        fallback = {
            "content": f"Hi, I saw that Stripe is hiring a {job.job_title} and noticed we have mutual connections there. I'd appreciate if you could introduce me."
        }

        try:
            raw_response = gateway.complete(
                prompt_id="referral_request.v1",
                user_content=user_content,
                temperature=0.3,
                use_cache=True,
            )

            if not raw_response:
                return fallback

            # Strip markdown code fences if present
            from app.ai import clean_json_content
            cleaned = clean_json_content(raw_response)

            parsed = json.loads(cleaned)
            # Ensure content key exists
            if "content" not in parsed:
                parsed["content"] = fallback["content"]

            return parsed

        except Exception:  # noqa: BLE001
            return fallback

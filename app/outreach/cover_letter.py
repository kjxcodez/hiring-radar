"""Personalized cover letter copywriter utilizing the AI Gateway."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Dict

if TYPE_CHECKING:
    from app.ai.gateway import AiGateway
    from app.models import Company, JobPosting
    from app.recommendation.profile import CandidateProfile


class CoverLetterGenerator:
    """Generates customized cover letters aligned with company mission."""

    @staticmethod
    def generate(
        candidate: CandidateProfile,
        job: JobPosting,
        company: Company,
        gateway: AiGateway,
    ) -> Dict[str, str]:
        """Call AI Gateway to draft a personalized cover letter."""
        context = {
            "candidate": {
                "skills": candidate.skills,
                "technologies": candidate.technologies,
                "experience": candidate.years_experience,
            },
            "job": {
                "title": job.job_title,
                "location": job.location,
            },
            "company": {
                "name": company.name,
                "description": company.description,
            },
        }

        user_content = json.dumps(context, indent=2)

        fallback = {
            "salutation": f"Dear hiring team at {company.name},",
            "opening": f"I am writing to express my interest in the {job.job_title} role.",
            "motivation": "I admire your company's mission and engineering approach.",
            "technical_alignment": f"With my background in software systems, I am confident in my alignment.",
            "closing": "Thank you for your time and consideration.",
            "full_letter": "",
        }

        try:
            raw_response = gateway.complete(
                prompt_id="cover_letter.v1",
                user_content=user_content,
                temperature=0.3,
                use_cache=True,
            )

            if not raw_response:
                fallback["full_letter"] = "\n\n".join(
                    [fallback["salutation"], fallback["opening"], fallback["motivation"], fallback["technical_alignment"], fallback["closing"]]
                )
                return fallback

            # Strip markdown code fences if present
            from app.ai import clean_json_content
            cleaned = clean_json_content(raw_response)

            parsed = json.loads(cleaned)
            # Ensure all required keys exist
            for k, default_val in fallback.items():
                if k not in parsed:
                    parsed[k] = default_val

            # Assemble full letter if not present or empty
            if not parsed.get("full_letter"):
                parsed["full_letter"] = "\n\n".join(
                    [parsed["salutation"], parsed["opening"], parsed["motivation"], parsed["technical_alignment"], parsed["closing"]]
                )

            return parsed

        except Exception:  # noqa: BLE001
            fallback["full_letter"] = "\n\n".join(
                [fallback["salutation"], fallback["opening"], fallback["motivation"], fallback["technical_alignment"], fallback["closing"]]
            )
            return fallback

"""AI Company Summarizer generating outreach talking points and technical overviews."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Dict, Optional

from loguru import logger

if TYPE_CHECKING:
    from app.ai.gateway import AiGateway
    from app.models import Company


_SAFE_DEFAULT = {
    "executive_summary": "—",
    "engineering_summary": "—",
    "why_join": "—",
    "potential_risks": "—",
    "resume_keywords": [],
    "outreach_talking_points": [],
}


class CompanySummarizer:
    """Interacts with the AI Gateway to generate high-density company reviews."""

    @staticmethod
    def summarize(
        company: Company,
        gateway: AiGateway,
        website_text: Optional[str] = None,
    ) -> Dict[str, any]:
        """Call AI Gateway to summarize company details and outreach points."""
        # Compile contextual text
        context_parts = []
        if company.description:
            context_parts.append(f"Company Description:\n{company.description}")
        if website_text:
            context_parts.append(f"Website Career Content:\n{website_text}")
        
        job_titles = [j.job_title for j in company.jobs if j.job_title]
        if job_titles:
            context_parts.append("Open Positions:\n" + "\n".join(f"- {t}" for t in job_titles))

        if not context_parts:
            return _SAFE_DEFAULT

        user_content = "\n\n---\n\n".join(context_parts)

        try:
            # Call the gateway using the versioned system prompt
            raw_response = gateway.complete(
                prompt_id="intelligence.v1",
                user_content=user_content,
                temperature=0.4,
                use_cache=True,
            )
            
            if not raw_response:
                return _SAFE_DEFAULT

            # Strip markdown fences if present
            from app.ai import clean_json_content
            cleaned = clean_json_content(raw_response)

            parsed = json.loads(cleaned)
            # Ensure all required keys exist
            for k, default_val in _SAFE_DEFAULT.items():
                if k not in parsed:
                    parsed[k] = default_val
            return parsed

        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "summarizer: AI generation failed for '{c}' — {exc}",
                c=company.name,
                exc=exc,
            )
            return _SAFE_DEFAULT

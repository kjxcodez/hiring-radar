"""Daily digest generator using AI to summarize change detection logs."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Dict, List, Any

if TYPE_CHECKING:
    from app.ai.gateway import AiGateway
    from app.monitoring.events import ChangeEvent


class DigestGenerator:
    """Invokes AI prompts to generate readable digests from events list."""

    @staticmethod
    def generate(
        events: List[ChangeEvent],
        gateway: AiGateway,
    ) -> Dict[str, Any]:
        """Summarize deterministic change events into structured daily digests."""
        events_data = []
        for ev in events:
            events_data.append({
                "type": ev.event_type,
                "company": ev.company_name,
                "job": ev.job_url,
                "prev": str(ev.previous_value),
                "curr": str(ev.current_value),
            })

        user_content = json.dumps(events_data, indent=2)

        fallback = {
            "executive_summary": f"Detected {len(events)} change events in the hiring pipeline.",
            "top_opportunities": [],
            "biggest_hiring_trends": [],
            "new_remote_roles": [],
            "recommendation_improvements": [],
            "companies_to_prioritize": [],
            "suggested_actions": ["Review raw event logs using 'hiring-radar monitor events'"],
        }

        if not events:
            fallback["executive_summary"] = "No new hiring pipeline events detected today."
            return fallback

        try:
            raw_response = gateway.complete(
                prompt_id="daily_digest.v1",
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

            # Ensure all required keys exist
            for k, default_val in fallback.items():
                if k not in parsed:
                    parsed[k] = default_val

            return parsed

        except Exception:  # noqa: BLE001
            return fallback

    @staticmethod
    def summarize_alert(
        event: ChangeEvent,
        gateway: AiGateway,
    ) -> str:
        """Call AI to format a short summary insight for an alert."""
        context = {
            "type": event.event_type,
            "company": event.company_name,
            "prev": str(event.previous_value),
            "curr": str(event.current_value),
        }
        
        user_content = json.dumps(context, indent=2)
        fallback = f"{event.event_type} at {event.company_name}: {event.previous_value} -> {event.current_value}"

        try:
            raw_response = gateway.complete(
                prompt_id="alert_summary.v1",
                user_content=user_content,
                temperature=0.3,
                use_cache=True,
            )

            if not raw_response:
                return fallback

            from app.ai import clean_json_content
            cleaned = clean_json_content(raw_response)

            parsed = json.loads(cleaned)
            return parsed.get("summary", fallback)

        except Exception:  # noqa: BLE001
            return fallback

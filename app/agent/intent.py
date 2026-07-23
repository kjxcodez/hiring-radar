"""Intent classification layer for the Hiring Radar conversational agent."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from pydantic import BaseModel
from app.config import settings

logger = logging.getLogger(__name__)


class IntentClassification(BaseModel):
    """Result of query intent classification."""
    intent: str
    confidence: float
    entities: dict[str, Any] = {}
    required_parameters: list[str] = []
    missing_parameters: list[str] = []
    suggested_workflow: Optional[str] = None


def classify_intent_rule_based(query: str) -> Optional[IntentClassification]:
    """Execute fast keyword-based heuristics to classify common commands with 100% confidence."""
    q = query.lower().strip()
    
    # 1. Greetings
    if q in ("hi", "hello", "hey", "howdy", "greetings"):
        return IntentClassification(intent="greeting", confidence=1.0)
        
    # 2. Help
    if q in ("help", "commands", "what can you do", "?"):
        return IntentClassification(intent="help", confidence=1.0)
        
    # 3. Diagnostics
    if q in ("agent doctor", "diagnostics", "agent diagnostics"):
        return IntentClassification(intent="diagnostics", confidence=1.0)
        
    # 4. Applications Status
    if any(w in q for w in ("show my applications", "list applications", "what applications", "my applications", "applications crm", "pending applications")):
        return IntentClassification(intent="application_status", confidence=1.0)
        
    # 5. Monitoring Alerts
    if any(w in q for w in ("show alerts", "list alerts", "any alerts", "monitoring alerts", "what alerts", "daily digest events")):
        return IntentClassification(intent="alerts", confidence=1.0)
        
    # 6. Company Research list
    if any(w in q for w in ("show companies", "what companies", "researched companies", "list companies")):
        return IntentClassification(intent="search_company", confidence=1.0)
        
    # 7. Follow-up
    if any(w in q for w in ("more like", "second one", "that one", "previous company", "the last one", "those jobs")):
        return IntentClassification(intent="follow_up", confidence=0.9)
        
    return None


def classify_intent(query: str, model: str | None = None) -> IntentClassification:
    """Classify the user query intent using rules or LLM fallback.

    Ensures the response fits one of the supported categories and returns structured entities.
    """
    # 1. Try rule-based fast classifier first
    rule_result = classify_intent_rule_based(query)
    if rule_result:
        return rule_result

    # 2. Fallback to LLM-based classification
    target_model = model or settings.openrouter_model
    if not settings.openrouter_api_key:
        return IntentClassification(intent="unknown", confidence=0.0)

    system_prompt = (
        "You are an intent classifier for the Hiring Radar job platform. Categorize the user query into one of these intents:\n"
        "- greeting (conversational hello)\n"
        "- help (asking for assistance/commands)\n"
        "- recommend_jobs (asking for job recommendations matching resume/skills)\n"
        "- search_jobs (looking for new job openings/listings)\n"
        "- search_company (list/search companies database)\n"
        "- company_research (request deep research on a specific company)\n"
        "- application_status (review CRM applications/status)\n"
        "- alerts (view monitoring events/alerts)\n"
        "- fit_score (compatibility/desirability calculation)\n"
        "- outreach (prepare/generate email drafts)\n"
        "- follow_up (contextual references to previous items)\n"
        "- diagnostics (doctor/inspector command)\n"
        "- unknown (unclear intent)\n\n"
        "Return a JSON object containing:\n"
        '{"intent": "intent_category", "confidence": 0.85, "entities": {"company_name": "Stripe", "job_title": "Backend"}, "missing_parameters": []}'
    )

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/kjxcodez/hiring-radar",
        "X-Title": "hiring-radar-intent-classifier",
    }
    
    json_body = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"}
    }

    try:
        import httpx
        with httpx.Client(timeout=10.0) as client:
            resp = client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=json_body)
            resp.raise_for_status()
            res = resp.json()
            content = res["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            return IntentClassification(
                intent=parsed.get("intent", "unknown"),
                confidence=parsed.get("confidence", 0.5),
                entities=parsed.get("entities", {}),
                required_parameters=parsed.get("required_parameters", []),
                missing_parameters=parsed.get("missing_parameters", []),
                suggested_workflow=parsed.get("suggested_workflow")
            )
    except Exception as exc:
        logger.warning("LLM intent classification failed: %s. Defaulting to unknown.", exc)
        return IntentClassification(intent="unknown", confidence=0.0)

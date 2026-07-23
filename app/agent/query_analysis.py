"""Structured query analyzer to extract search filters and parameters."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from pydantic import BaseModel
from app.config import settings

logger = logging.getLogger(__name__)


class QueryAnalysis(BaseModel):
    """Extracted structural search filters from a user query."""
    job_titles: list[str] = []
    locations: list[str] = []
    remote_preferred: Optional[bool] = None
    salary_expectation: Optional[str] = None
    technologies: list[str] = []
    experience_level: Optional[str] = None
    company_names: list[str] = []
    industry: Optional[str] = None
    time_constraints: Optional[str] = None
    urgency: Optional[str] = None


def analyze_query_rule_based(query: str) -> Optional[QueryAnalysis]:
    """Fast local parsing of common filter phrases."""
    q = query.lower()
    
    # 1. Simple remote checks
    remote = None
    if "remote" in q:
        remote = True
    elif "onsite" in q or "hybrid" in q:
        remote = False
        
    # Check for simple job titles / techs / locations
    job_titles = []
    locations = []
    technologies = []
    
    if "backend" in q:
        job_titles.append("backend")
    if "frontend" in q:
        job_titles.append("frontend")
    if "software" in q:
        job_titles.append("software")
        
    if "europe" in q:
        locations.append("Europe")
    if "usa" in q or "us" in q or "united states" in q:
        locations.append("USA")
        
    if "python" in q:
        technologies.append("python")
    if "javascript" in q or "typescript" in q:
        technologies.append("typescript")

    if job_titles or locations or technologies or remote is not None:
        return QueryAnalysis(
            job_titles=job_titles,
            locations=locations,
            remote_preferred=remote,
            technologies=technologies
        )
    return None


def analyze_query(query: str, model: str | None = None) -> QueryAnalysis:
    """Analyze query to parse detailed parameters using LLM structuring."""
    # 1. Run local fast rule matching
    rule_res = analyze_query_rule_based(query)
    if rule_res:
        return rule_res

    # 2. LLM structuring fallback
    target_model = model or settings.openrouter_model
    if not settings.openrouter_api_key:
        return QueryAnalysis()

    system_prompt = (
        "You are a structured query analyzer for a hiring platform. Extract search filters from the user's message.\n"
        "Output a JSON object with this schema:\n"
        '{"job_titles": ["backend"], "locations": ["Europe"], "remote_preferred": true, "salary_expectation": ">90k", "technologies": ["python"], "experience_level": "senior", "company_names": []}'
    )

    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/kjxcodez/hiring-radar",
        "X-Title": "hiring-radar-query-analyzer",
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
            return QueryAnalysis(
                job_titles=parsed.get("job_titles") or [],
                locations=parsed.get("locations") or [],
                remote_preferred=parsed.get("remote_preferred"),
                salary_expectation=parsed.get("salary_expectation"),
                technologies=parsed.get("technologies") or [],
                experience_level=parsed.get("experience_level"),
                company_names=parsed.get("company_names") or [],
                industry=parsed.get("industry"),
                time_constraints=parsed.get("time_constraints"),
                urgency=parsed.get("urgency")
            )
    except Exception as exc:
        logger.warning("Query analysis extraction failed: %s. Returning default.", exc)
        return QueryAnalysis()

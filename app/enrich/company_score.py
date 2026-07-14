"""AI-driven company attractiveness scoring engine.

Evaluates a company's quality and desirability across five axes using OpenRouter
and synthesizes an overall rating and rationale.
"""

from __future__ import annotations

import json
from datetime import datetime

import httpx
from loguru import logger
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.models import Company
from app.utils import get_http_client


_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _post_with_retry(client: httpx.Client, headers: dict, json_body: dict) -> httpx.Response:
    """POST to OpenRouter API, retrying only on transient connection/timeout errors."""
    resp = client.post(_OPENROUTER_URL, headers=headers, json=json_body)
    resp.raise_for_status()
    return resp


def _clean_json_content(content: str) -> str:
    """Strip accidental markdown code fences (e.g. ```json ... ```) from the LLM output."""
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def build_system_prompt() -> str:
    """Build the system prompt for the attractiveness scoring task."""
    return (
        "You are an expert AI corporate analyst and career consultant.\n"
        "Your task is to analyze details about a company and produce structured JSON ratings "
        "evaluating the company's quality and desirability as an employer.\n\n"
        "You must output a single, raw JSON object (and nothing else) with the following structure:\n"
        "{\n"
        '  "growth": <int, 1-10 rating for growth trajectory/potential>,\n'
        '  "engineering_culture": <int, 1-10 rating for engineering culture/practices>,\n'
        '  "remote_friendliness": <int, 1-10 rating for remote-first work environment/compatibility>,\n'
        '  "open_source_presence": <int, 1-10 rating for open-source or public tech contribution>,\n'
        '  "hiring_urgency": <int, 1-10 rating for hiring signals/urgency>,\n'
        '  "overall": <float, 0-10 overall synthesized quality rating (reasoned, not a simple average)>,\n'
        '  "rationale": "<a concise one-sentence explanation justifying the scores>"\n'
        "}\n\n"
        "Guidelines:\n"
        "1. Do NOT use markdown code fences (like ```json). Return ONLY the raw JSON string.\n"
        "2. Score based ONLY on the provided signal details. Be conservative when data is sparse or missing; "
        "rate those axes very low (e.g., 1-3) instead of assuming/inventing details.\n"
        "3. All ratings except overall must be integers between 1 and 10. overall must be a float between 0 and 10.\n"
    )


def build_scoring_prompt(company: Company) -> str:
    """Build the user prompt combining description, research notes, AI summaries, and jobs count."""
    desc = company.description or "No description available."
    ai_summary = company.ai_summary or "No summary available."
    talking_points = ", ".join(company.ai_talking_points) if company.ai_talking_points else "None available."
    job_count = len(company.jobs)
    
    # Format research notes safely
    res_notes = company.research_notes or {}
    research_text = (
        f"Products: {res_notes.get('products', '-')}\n"
        f"Likely Customers: {res_notes.get('likely_customers', '-')}\n"
        f"Engineering Notes: {res_notes.get('engineering_notes', '-')}\n"
        f"Recent Signals: {res_notes.get('recent_signals', '-')}"
    )

    return (
        f"Company Details:\n"
        f"Name: {company.name}\n"
        f"Description: {desc}\n"
        f"AI Summary: {ai_summary}\n"
        f"AI Hook Points: {talking_points}\n"
        f"Job Postings Count: {job_count}\n\n"
        f"Deeper Corporate Research Notes:\n"
        f"{research_text}\n"
    )


def score_company_attractiveness(
    company: Company,
    model: str | None = None,
    dry_run: bool = False,
) -> Company:
    """Evaluate a company's quality and desirability across five axes using OpenRouter.

    Args:
        company: The Company object to score (mutated in-place).
        model: Optional model override. Defaults to settings.openrouter_model.
        dry_run: If True, logs the prompts to be sent and returns the company unmodified.

    Returns:
        The updated Company object.
    """
    # 1. API key verification
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Please add it to your .env file."
        )

    # 2. Build prompts
    sys_prompt = build_system_prompt()
    user_prompt = build_scoring_prompt(company)

    # 3. Handle dry run
    if dry_run:
        logger.info(
            "dry-run: attractiveness prompt preview for '{company}'\n"
            "--- SYSTEM PROMPT ---\n{sys}\n"
            "--- USER PROMPT ---\n{user}\n"
            "---------------------",
            company=company.name,
            sys=sys_prompt,
            user=user_prompt,
        )
        return company

    # 4. Perform POST call
    target_model = model or settings.openrouter_model
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/<placeholder>/hiring-radar",
        "X-Title": "hiring-radar",
    }
    json_body = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    try:
        with get_http_client() as client:
            response = _post_with_retry(client, headers, json_body)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "score-attractiveness/{company}: OpenRouter API returned HTTP {status} — skipping",
            company=company.name,
            status=exc.response.status_code,
        )
        company.notes.append(f"score_attractiveness_failed: API returned HTTP {exc.response.status_code}")
        return company
    except (httpx.TimeoutException, httpx.ConnectError, RetryError) as exc:
        logger.warning(
            "score-attractiveness/{company}: connection failed after retries — {exc}",
            company=company.name,
            exc=exc,
        )
        company.notes.append(f"score_attractiveness_failed: network error — {exc}")
        return company
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "score-attractiveness/{company}: unexpected API call error — {exc}",
            company=company.name,
            exc=exc,
        )
        company.notes.append(f"score_attractiveness_failed: unexpected error — {exc}")
        return company

    # 5. Parse and apply result
    try:
        payload = response.json()
        raw_content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning(
            "score-attractiveness/{company}: failed to extract text from API response — {exc}",
            company=company.name,
            exc=exc,
        )
        company.notes.append(f"score_attractiveness_failed: invalid API response — {exc}")
        return company

    try:
        clean_json = _clean_json_content(raw_content)
        parsed = json.loads(clean_json)

        growth = int(parsed.get("growth") or 1)
        engineering_culture = int(parsed.get("engineering_culture") or 1)
        remote_friendliness = int(parsed.get("remote_friendliness") or 1)
        open_source_presence = int(parsed.get("open_source_presence") or 1)
        hiring_urgency = int(parsed.get("hiring_urgency") or 1)
        overall = float(parsed.get("overall") or 0.0)
        rationale = parsed.get("rationale") or "—"

        company.company_scores = {
            "growth": growth,
            "engineering_culture": engineering_culture,
            "remote_friendliness": remote_friendliness,
            "open_source_presence": open_source_presence,
            "hiring_urgency": hiring_urgency,
        }
        company.company_score_overall = overall
        company.notes.append(f"score_rationale: {rationale}")
        company.last_updated = datetime.now()

        logger.info("score-attractiveness/{company}: successfully scored", company=company.name)

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "score-attractiveness/{company}: failed to parse/apply LLM JSON content — {exc}",
            company=company.name,
            exc=exc,
        )
        company.notes.append("score_attractiveness_failed: could not parse response")

    return company

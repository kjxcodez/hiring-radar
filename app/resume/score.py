"""AI-based resume compatibility scoring engine using OpenRouter.

Compares a candidate's resume text to a company's profile and job postings
to generate compatibility ratings, skill breakdowns, and gap analysis.
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

# Safe default return dict in case of dry_run, API failure or parse failure
_SAFE_DEFAULT = {
    "overall_match_percent": 0,
    "skill_breakdown": {},
    "missing_skills": [],
}


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
    """Build the system prompt for the resume scoring task."""
    return (
        "You are an expert career intelligence AI agent. Your job is to compare a candidate's resume "
        "to a company's job openings and profile to determine matching compatibility.\n\n"
        "You must output a single, raw JSON object (and nothing else) with the following structure:\n"
        "{\n"
        '  "overall_match_percent": <int, 0 to 100 representing overall compatibility>,\n'
        '  "skill_breakdown": {\n'
        '    "<skill_name>": <int, rating 1 to 5 representing candidate\'s proficiency or match strength based on resume>,\n'
        "    ...\n"
        "  },\n"
        '  "missing_skills": [\n'
        '    "<skill_name_missing_but_needed>",\n'
        "    ...\n"
        "  ]\n"
        "}\n\n"
        "Guidelines:\n"
        "1. Do NOT use markdown code fences (like ```json). Return ONLY the raw JSON string.\n"
        "2. Do NOT hallucinate a fixed, generic checklist of skills. Infer relevant skills and technologies "
        "dynamically from the company's active job titles, job descriptions, and profile.\n"
        "3. Be conservative and highly specific. Do not give inflated scores or ratings unless clearly "
        "justified by the candidate's resume.\n"
        "4. Ensure all ratings in \"skill_breakdown\" are integers between 1 and 5.\n"
    )


def build_scoring_prompt(company: Company, resume_text: str) -> str:
    """Build the user prompt containing company details, job postings, and the resume text."""
    # Build jobs text representation
    jobs_list = []
    if company.jobs:
        for idx, job in enumerate(company.jobs, 1):
            title = job.job_title or "Job Title N/A"
            location = job.location or "Location N/A"
            remote = job.remote_type or "unknown"
            jobs_list.append(
                f"Job #{idx}:\n"
                f"  Title: {title}\n"
                f"  Location: {location} ({remote})\n"
            )
    jobs_text = "\n".join(jobs_list) if jobs_list else "No active job postings listed."

    company_desc = company.description or "No company description available."

    return (
        f"Company Profile:\n"
        f"Name: {company.name}\n"
        f"Description: {company_desc}\n\n"
        f"Active Job Openings:\n"
        f"{jobs_text}\n\n"
        f"Candidate's Resume Text:\n"
        f"---\n"
        f"{resume_text}\n"
        f"---\n"
    )


def score_company(
    company: Company,
    resume_text: str,
    model: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Evaluate a company's compatibility with a resume using OpenRouter.

    Args:
        company: The Company object to evaluate.
        resume_text: The raw text content of the candidate's resume.
        model: Optional model override. Defaults to settings.openrouter_model.
        dry_run: If True, logs the prompts to be sent and returns safe default metrics.

    Returns:
        A dict matching {"overall_match_percent": int, "skill_breakdown": dict, "missing_skills": list}
    """
    # 1. API key verification
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Please add it to your .env file."
        )

    # 2. Build prompts
    sys_prompt = build_system_prompt()
    user_prompt = build_scoring_prompt(company, resume_text)

    # 3. Handle dry run
    if dry_run:
        logger.info(
            "dry-run: scoring prompt preview for '{company}'\n"
            "--- SYSTEM PROMPT ---\n{sys}\n"
            "--- USER PROMPT ---\n{user}\n"
            "---------------------",
            company=company.name,
            sys=sys_prompt,
            user=user_prompt,
        )
        return _SAFE_DEFAULT

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
            "score/{company}: OpenRouter API returned HTTP {status} — skipping score calculation",
            company=company.name,
            status=exc.response.status_code,
        )
        return _SAFE_DEFAULT
    except (httpx.TimeoutException, httpx.ConnectError, RetryError) as exc:
        logger.warning(
            "score/{company}: connection failed after retries — {exc}",
            company=company.name,
            exc=exc,
        )
        return _SAFE_DEFAULT
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "score/{company}: unexpected API call error — {exc}",
            company=company.name,
            exc=exc,
        )
        return _SAFE_DEFAULT

    # 5. Parse result
    try:
        payload = response.json()
        raw_content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning(
            "score/{company}: failed to extract text from API response — {exc}",
            company=company.name,
            exc=exc,
        )
        return _SAFE_DEFAULT

    try:
        clean_json = _clean_json_content(raw_content)
        parsed = json.loads(clean_json)

        # Extract & validate fields defensively
        overall_match = parsed.get("overall_match_percent")
        skill_breakdown = parsed.get("skill_breakdown")
        missing_skills = parsed.get("missing_skills")

        if overall_match is None or skill_breakdown is None or missing_skills is None:
            raise ValueError("Parsed JSON response missing one or more required keys.")

        logger.info("score/{company}: successfully scored", company=company.name)
        return {
            "overall_match_percent": int(overall_match),
            "skill_breakdown": dict(skill_breakdown),
            "missing_skills": list(missing_skills),
        }

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "score/{company}: failed to parse/apply LLM JSON content — {exc}",
            company=company.name,
            exc=exc,
        )
        return _SAFE_DEFAULT

"""AI-powered subject line generator for cold email outreach.

Uses OpenRouter to generate distinct, targeted cold-email subject lines.
"""

from __future__ import annotations

import json

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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ---------------------------------------------------------------------------
# Retry-wrapped API call (transient network errors only)
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),  # 1 initial + 2 retries
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


# ---------------------------------------------------------------------------
# Prompt Builders
# ---------------------------------------------------------------------------

def build_subject_system_prompt() -> str:
    """Return the system prompt for generating email subject lines."""
    return (
        "You are an assistant helping write highly effective, non-generic, "
        "and non-spammy cold email subject lines. Follow these rules:\n"
        "- Under 60 characters in length.\n"
        "- No exclamation points or clickbait phrasing.\n"
        "- Keep the tone professional, curious, or value-prop focused.\n"
        "- Do not mention or use placeholders; return fully fleshed out subject lines.\n"
        "- Answer with ONLY a raw JSON array of strings, no markdown formatting."
    )


def build_subject_prompt(company: Company, count: int) -> str:
    """Construct a user prompt to generate count distinct subject lines for reaching out to company."""
    # Active jobs for context
    jobs_str = ", ".join(f"'{j.job_title}'" for j in company.jobs[:3]) or "open roles"
    
    context = (
        f"Company Name: {company.name}\n"
        f"AI Summary: {company.ai_summary or 'None'}\n"
        f"AI Talking Points: {'; '.join(company.ai_talking_points) if company.ai_talking_points else 'None'}\n"
        f"Active Openings: {jobs_str}\n"
    )

    return f"""Based on the following company data, generate {count} distinct cold email subject lines:

{context}

Generate exactly {count} distinct subject lines suitable for reaching out to someone at this company.
Varied styles to try:
- Direct (referencing the active roles or department).
- Curious (asking a quick question related to their operations or stack).
- Value-prop/hook (referencing their work or talking points).

Return a valid JSON array of strings, formatted as raw JSON without markdown fences (no ```json or ```) or preamble:
[
  "Subject Line 1",
  "Subject Line 2",
  ...
]
"""


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def generate_subject_lines(
    company: Company,
    count: int = 10,
    model: str | None = None,
    dry_run: bool = False,
) -> list[str]:
    """Generate multiple distinct subject line candidates for outreach to the target company.

    Args:
        company: The Company object containing data.
        count: Number of candidate subject lines to produce.
        model: Optional model override. Defaults to settings.openrouter_model.
        dry_run: If True, logs the prompts to be sent and returns an empty list.

    Returns:
        List of generated subject line strings, or empty list on failure.
    """
    # 1. API key verification
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Please add it to your .env file."
        )

    # 2. Build prompts
    sys_prompt = build_subject_system_prompt()
    user_prompt = build_subject_prompt(company, count)

    # 3. Handle dry run
    if dry_run:
        logger.info(
            "dry-run: subject lines prompt preview for '{company}'\n"
            "--- SYSTEM PROMPT ---\n{sys}\n"
            "--- USER PROMPT ---\n{user}\n"
            "---------------------",
            company=company.name,
            sys=sys_prompt,
            user=user_prompt,
        )
        return []

    # 4. Perform API call
    target_model = model or settings.openrouter_model
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        # Required OpenRouter headers
        "HTTP-Referer": "https://github.com/<placeholder>/hiring-radar",
        "X-Title": "hiring-radar",
    }
    json_body = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.5,
    }

    try:
        with get_http_client() as client:
            response = _post_with_retry(client, headers, json_body)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "outreach/subjects/{company}: OpenRouter API call failed — {exc}",
            company=company.name,
            exc=exc,
        )
        return []

    # 5. Parse JSON array
    try:
        payload = response.json()
        raw_content = payload["choices"][0]["message"]["content"]
        clean_json = _clean_json_content(raw_content)
        parsed = json.loads(clean_json)

        if not isinstance(parsed, list):
            raise ValueError("Expected JSON response to be a list of strings.")

        subjects = [str(item).strip() for item in parsed if item]
        logger.info(
            "outreach/subjects/{company}: successfully generated {n} subject lines",
            company=company.name,
            n=len(subjects),
        )
        return subjects

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "outreach/subjects/{company}: failed to parse/apply LLM response — {exc}",
            company=company.name,
            exc=exc,
        )
        return []

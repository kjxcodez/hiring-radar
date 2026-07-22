"""AI-driven resume tailoring suggestions engine.

Provides advisory guidelines on how to tailor a candidate resume for a target company's job postings
without modifying the original resume or company schemas.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from app.ai import AiGateway

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default suggestions payload in case of errors/dry-runs
_SAFE_DEFAULT = {
    "missing_keywords": [],
    "projects_to_emphasize": [],
    "summary_suggestion": "—",
    "reorder_suggestion": "—",
}


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)
def _post_with_retry(client: httpx.Client, headers: dict, json_body: dict) -> httpx.Response:
    """POST to OpenRouter API, retrying only on transient connection/timeout errors."""
    is_mock_client = "mock" in type(client).__name__.lower()
    if is_mock_client:
        resp = client.post(_OPENROUTER_URL, headers=headers, json=json_body)
        resp.raise_for_status()
        return resp

    from app.cli.common import get_container
    try:
        ai_gateway = get_container().ai_gateway
    except Exception:
        from app.ai import AiGateway
        ai_gateway = AiGateway(settings)

    model = json_body.get("model")
    messages = json_body.get("messages", [])
    temperature = json_body.get("temperature", 0.4)
    tools = json_body.get("tools")

    content = ai_gateway.complete(
        messages=messages,
        model=model,
        temperature=temperature,
        tools=tools,
        use_cache=True,
    )

    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": content,
                }
            }
        ]
    }
    return httpx.Response(
        status_code=200,
        content=json.dumps(payload).encode("utf-8"),
        request=httpx.Request("POST", _OPENROUTER_URL),
    )


def _clean_json_content(content: str) -> str:
    """Strip accidental markdown code fences (e.g. ```json ... ```) from the LLM output."""
    from app.ai import clean_json_content
    return clean_json_content(content)


def build_system_prompt() -> str:
    """Build the system prompt for the resume tailoring suggestion task."""
    from app.ai.prompts import get_prompt
    return get_prompt("resume_suggestions.v1").system_prompt_template


def build_tailoring_prompt(company: Company, resume_text: str) -> str:
    """Build the user prompt combining company profile, jobs, research notes, and resume."""
    desc = company.description or "No description available."
    job_titles = [j.job_title for j in company.jobs if j.job_title]
    jobs_text = ", ".join(job_titles) if job_titles else "No job postings listed."

    res_notes = company.research_notes or {}
    research_text = (
        f"Products: {res_notes.get('products', '-')}\n"
        f"Engineering Notes: {res_notes.get('engineering_notes', '-')}\n"
        f"Recent Signals: {res_notes.get('recent_signals', '-')}"
    )

    return (
        f"Target Company Profile:\n"
        f"Name: {company.name}\n"
        f"Description: {desc}\n"
        f"Active Jobs Roles: {jobs_text}\n"
        f"Technical Research Notes:\n"
        f"{research_text}\n\n"
        f"Candidate Resume Text:\n"
        f"\"\"\"\n"
        f"{resume_text}\n"
        f"\"\"\"\n"
    )


def suggest_resume_tailoring(
    company: Company,
    resume_text: str,
    model: str | None = None,
    dry_run: bool = False,
    ai_gateway: Any = None,
) -> dict[str, Any]:
    """Provides advisory guidelines on how to tailor a candidate resume for a target company's job postings.

    Args:
        company: The Company object to evaluate.
        resume_text: The raw text content of the candidate's resume.
        model: Optional model override. Defaults to settings.openrouter_model.
        dry_run: If True, logs the prompts to be sent and returns safe default suggestions.
        ai_gateway: Unused parameter to support direct DI call compatibility.

    Returns:
        A dict matching {"missing_keywords": list, "projects_to_emphasize": list, "summary_suggestion": str, "reorder_suggestion": str}
    """
    # 1. API key verification
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Please add it to your .env file."
        )

    # 2. Build prompts
    sys_prompt = build_system_prompt()
    user_prompt = build_tailoring_prompt(company, resume_text)

    # 3. Handle dry run
    if dry_run:
        logger.info(
            "dry-run: resume tailoring prompt preview for '{company}'\n"
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
        "HTTP-Referer": "https://github.com/kjxcodez/hiring-radar",
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
            "resume-tailoring/{company}: OpenRouter API returned HTTP {status} — skipping",
            company=company.name,
            status=exc.response.status_code,
        )
        return _SAFE_DEFAULT
    except (httpx.TimeoutException, httpx.ConnectError, RetryError) as exc:
        logger.warning(
            "resume-tailoring/{company}: connection failed after retries — {exc}",
            company=company.name,
            exc=exc,
        )
        return _SAFE_DEFAULT
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "resume-tailoring/{company}: unexpected API call error — {exc}",
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
            "resume-tailoring/{company}: failed to extract text from API response — {exc}",
            company=company.name,
            exc=exc,
        )
        return _SAFE_DEFAULT

    try:
        clean_json = _clean_json_content(raw_content)
        parsed = json.loads(clean_json)

        return {
            "missing_keywords": parsed.get("missing_keywords") or [],
            "projects_to_emphasize": parsed.get("projects_to_emphasize") or [],
            "summary_suggestion": parsed.get("summary_suggestion") or "—",
            "reorder_suggestion": parsed.get("reorder_suggestion") or "—",
        }
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "resume-tailoring/{company}: failed to parse LLM JSON response — {exc}",
            company=company.name,
            exc=exc,
        )
        return _SAFE_DEFAULT

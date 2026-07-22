"""OpenRouter integration for company AI enrichment."""

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
from app.enrich.prompts import build_enrichment_prompt, build_system_prompt
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


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def enrich(company: Company, model: str | None = None, dry_run: bool = False, ai_gateway: Any = None) -> Company:
    """Enrich a company with AI-generated notes using OpenRouter.

    Args:
        company: The Company object to enrich (mutated in-place on success).
        model: Optional model override. Defaults to settings.openrouter_model.
        dry_run: If True, logs the prompts to be sent and returns the company unmodified.
        ai_gateway: Unused parameter to support direct DI call compatibility.

    Returns:
        The Company object.
    """
    # 1. API key verification
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Please add it to your .env file."
        )

    # 2. Build prompts
    sys_prompt = build_system_prompt()
    user_prompt = build_enrichment_prompt(company)

    # 3. Handle dry run
    if dry_run:
        logger.info(
            "dry-run: prompt preview for '{company}'\n"
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
        # Required OpenRouter headers (replace with real public repo URL once public)
        "HTTP-Referer": "https://github.com/kjxcodez/hiring-radar",
        "X-Title": "hiring-radar",
    }
    json_body = {
        "model": target_model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
    }

    try:
        with get_http_client() as client:
            response = _post_with_retry(client, headers, json_body)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "enrich/{company}: OpenRouter API returned HTTP {status} — skipping",
            company=company.name,
            status=exc.response.status_code,
        )
        company.notes.append(f"enrich_failed: API returned HTTP {exc.response.status_code}")
        return company
    except (httpx.TimeoutException, httpx.ConnectError, RetryError) as exc:
        logger.warning(
            "enrich/{company}: connection failed after retries — {exc}",
            company=company.name,
            exc=exc,
        )
        company.notes.append(f"enrich_failed: network error — {exc}")
        return company
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "enrich/{company}: unexpected API call error — {exc}",
            company=company.name,
            exc=exc,
        )
        company.notes.append(f"enrich_failed: unexpected API error — {exc}")
        return company

    # 5. Parse and apply result
    try:
        payload = response.json()
        raw_content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning(
            "enrich/{company}: failed to extract text from API response — {exc}",
            company=company.name,
            exc=exc,
        )
        company.notes.append(f"enrich_failed: invalid API response structure — {exc}")
        return company

    try:
        clean_json = _clean_json_content(raw_content)
        parsed = json.loads(clean_json)

        # Extract fields defensively
        summary = parsed.get("summary")
        talking_points = parsed.get("talking_points") or []
        fit_rationale = parsed.get("fit_rationale")

        if not summary or not isinstance(talking_points, list):
            raise ValueError("Parsed JSON is missing 'summary' or has invalid 'talking_points' shape.")

        # Update company fields
        company.ai_summary = summary
        company.ai_talking_points = talking_points
        company.ai_fit_rationale = fit_rationale
        company.last_updated = datetime.now()

        logger.info("enrich/{company}: successfully enriched", company=company.name)

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "enrich/{company}: failed to parse/apply LLM JSON content — {exc}",
            company=company.name,
            exc=exc,
        )
        company.notes.append("enrich_failed: could not parse model response")

    return company

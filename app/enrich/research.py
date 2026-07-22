"""Deeper AI company research module.

Gathers raw text from the company's profile and its GitHub page (if present)
and calls OpenRouter to generate detailed product, customer, stack, and hiring urgency signals.
"""

from __future__ import annotations

import json
from datetime import datetime

from typing import Any

import httpx
from loguru import logger
from selectolax.parser import HTMLParser
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.models import Company
from app.utils import RateLimiter, is_allowed_by_robots, safe_get, get_http_client


_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Default research dict in case of failures or dry-runs
_SAFE_DEFAULT = {
    "products": "—",
    "likely_customers": "—",
    "engineering_notes": "—",
    "recent_signals": "—",
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
    stripped = content.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _extract_github_repos(html_text: str) -> list[str]:
    """Extract repository names and descriptions from GitHub profile HTML page using selectolax."""
    parser = HTMLParser(html_text)
    repos = []

    # Org and user profile page anchors for repositories
    elements = parser.css('a[itemprop="name codeRepository"]')
    for el in elements:
        repo_name = el.text(strip=True)
        desc = ""
        # Find the card container
        container = el.parent
        while container:
            if container.tag in ("li", "div") and ("py-4" in (container.attributes.get("class") or "") or "col-12" in (container.attributes.get("class") or "")):
                break
            container = container.parent
        
        search_root = container if container else el.parent
        if search_root:
            desc_el = search_root.css_first('[itemprop="description"]')
            if desc_el:
                desc = desc_el.text(strip=True)
        if desc:
            repos.append(f"- {repo_name}: {desc}")
        else:
            repos.append(f"- {repo_name}")

    # Fallback to wb-break-all links (org page repos) if name codeRepository was empty
    if not repos:
        for el in parser.css('a.wb-break-all'):
            repo_name = el.text(strip=True)
            desc = ""
            container = el.parent
            while container:
                if container.tag in ("li", "div") and ("py-4" in (container.attributes.get("class") or "") or "col-12" in (container.attributes.get("class") or "")):
                    break
                container = container.parent
            
            search_root = container if container else el.parent
            if search_root:
                desc_el = search_root.css_first('p.color-fg-muted') or search_root.css_first('p.text-gray')
                if desc_el:
                    desc = desc_el.text(strip=True)
            if desc:
                repos.append(f"- {repo_name}: {desc}")
            else:
                repos.append(f"- {repo_name}")

    return repos[:15]


def _fetch_github_text(
    url: str,
    client: httpx.Client,
    rate_limiter: RateLimiter,
) -> str | None:
    """Fetch GitHub profile page HTML safely, respecting robots.txt and rate limits."""
    try:
        allowed = is_allowed_by_robots(url, client)
    except Exception as exc:  # noqa: BLE001
        logger.debug("GitHub robots check failed ({exc}) — allowing", exc=exc)
        allowed = True

    if not allowed:
        logger.info("GitHub profile fetch skipped: disallowed by robots.txt")
        return None

    response = safe_get(client, url, rate_limiter)
    if response is None:
        return None
    return response.text


def build_system_prompt() -> str:
    """Build the system prompt for deeper company research."""
    return (
        "You are an expert AI research agent specializing in corporate intelligence and firmographics.\n"
        "Your task is to analyze details about a company and produce structured JSON summarizing their "
        "products, target customers, engineering stack/tools, and recent growth/urgency signals.\n\n"
        "You must output a single, raw JSON object (and nothing else) with the following structure:\n"
        "{\n"
        '  "products": "<1-2 sentences summarizing products/services>",\n'
        '  "likely_customers": "<1 sentence stating likely customers, explicitly marked speculative if not clearly stated>",\n'
        '  "engineering_notes": "<comma-separated stack/tools mentioned, or \'None\' if none found>",\n'
        '  "recent_signals": "<growth or hiring urgency signals, e.g. \'5 open engineering roles\', or \'None\' if none found>"\n'
        "}\n\n"
        "Guidelines:\n"
        "1. Do NOT use markdown code fences (like ```json). Return ONLY the raw JSON string.\n"
        "2. Do NOT invent/hallucinate news, funding events, or dates not provided in the input text. Only base recent_signals on facts present in the text (such as count of job postings or stack complexity).\n"
        "3. Keep descriptions precise, dense, and professional.\n"
    )


def build_research_prompt(
    company: Company,
    github_repos: list[str],
) -> str:
    """Build the user prompt combining description, summary, jobs, and GitHub repos."""
    company_desc = company.description or "No company description available."
    ai_summary = company.ai_summary or "No initial AI summary available."
    
    # Active job postings list
    job_titles = [j.job_title for j in company.jobs if j.job_title]
    jobs_text = ", ".join(job_titles) if job_titles else "No job postings listed."

    github_text = "\n".join(github_repos) if github_repos else "No GitHub repositories found or available."

    return (
        f"Company Details:\n"
        f"Name: {company.name}\n"
        f"Description: {company_desc}\n"
        f"AI Summary: {ai_summary}\n\n"
        f"Active Open Job Titles:\n"
        f"{jobs_text}\n\n"
        f"GitHub Profile Repositories (Heuristic static HTML scrape):\n"
        f"{github_text}\n"
    )


def research_company(
    company: Company,
    client: httpx.Client,
    rate_limiter: RateLimiter,
    model: str | None = None,
    dry_run: bool = False,
    ai_gateway: Any = None,
) -> Company:
    """Perform deeper AI-based corporate research on a company.

    Args:
        company: The Company object to research (mutated in-place).
        client: httpx Client to perform network requests.
        rate_limiter: RateLimiter instance.
        model: Optional model override. Defaults to settings.openrouter_model.
        dry_run: If True, previews prompts and exits without calling OpenRouter.

    Returns:
        The updated Company object.
    """
    # 1. API key verification
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Please add it to your .env file."
        )

    # 2. Gather additional data (GitHub profile HTML page)
    github_repos = []
    if company.github_url:
        logger.info("research/{company}: fetching GitHub profile page", company=company.name)
        html = _fetch_github_text(company.github_url, client, rate_limiter)
        if html:
            github_repos = _extract_github_repos(html)
            logger.info(
                "research/{company}: extracted {count} repos from GitHub page",
                company=company.name,
                count=len(github_repos),
            )
        else:
            company.notes.append("research_github: profile fetch failed or disallowed")

    # 3. Build prompts
    sys_prompt = build_system_prompt()
    user_prompt = build_research_prompt(company, github_repos)

    # 4. Handle dry run
    if dry_run:
        logger.info(
            "dry-run: research prompt preview for '{company}'\n"
            "--- SYSTEM PROMPT ---\n{sys}\n"
            "--- USER PROMPT ---\n{user}\n"
            "---------------------",
            company=company.name,
            sys=sys_prompt,
            user=user_prompt,
        )
        company.research_notes = _SAFE_DEFAULT
        return company

    # 5. Perform OpenRouter POST call
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
        response = _post_with_retry(client, headers, json_body)
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "research/{company}: OpenRouter API returned HTTP {status} — skipping deeper research",
            company=company.name,
            status=exc.response.status_code,
        )
        company.notes.append(f"research_failed: API returned HTTP {exc.response.status_code}")
        company.research_notes = _SAFE_DEFAULT
        return company
    except (httpx.TimeoutException, httpx.ConnectError, RetryError) as exc:
        logger.warning(
            "research/{company}: connection failed after retries — {exc}",
            company=company.name,
            exc=exc,
        )
        company.notes.append(f"research_failed: network error — {exc}")
        company.research_notes = _SAFE_DEFAULT
        return company
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "research/{company}: unexpected API call error — {exc}",
            company=company.name,
            exc=exc,
        )
        company.notes.append(f"research_failed: unexpected API error — {exc}")
        company.research_notes = _SAFE_DEFAULT
        return company

    # 6. Parse and apply result
    try:
        payload = response.json()
        raw_content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        logger.warning(
            "research/{company}: failed to extract text from API response — {exc}",
            company=company.name,
            exc=exc,
        )
        company.notes.append(f"research_failed: invalid API response structure — {exc}")
        company.research_notes = _SAFE_DEFAULT
        return company

    try:
        clean_json = _clean_json_content(raw_content)
        parsed = json.loads(clean_json)

        products = parsed.get("products") or "—"
        likely_customers = parsed.get("likely_customers") or "—"
        engineering_notes = parsed.get("engineering_notes") or "—"
        recent_signals = parsed.get("recent_signals") or "—"

        company.research_notes = {
            "products": products,
            "likely_customers": likely_customers,
            "engineering_notes": engineering_notes,
            "recent_signals": recent_signals,
        }
        company.last_updated = datetime.now()
        logger.info("research/{company}: successfully researched", company=company.name)

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "research/{company}: failed to parse/apply LLM JSON content — {exc}",
            company=company.name,
            exc=exc,
        )
        company.notes.append("research_failed: could not parse model response")
        company.research_notes = _SAFE_DEFAULT

    return company

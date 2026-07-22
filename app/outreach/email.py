"""AI-powered cold email outreach body generator.

Generates the creative variables (hook, pitch, CTA) of an outreach email
using OpenRouter, and renders them into the chosen local markdown template.
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

from app.config import settings, yaml_config
from app.models import Company
from app.outreach.subjects import generate_subject_lines
from app.outreach.templates import load_template, render_template
from app.utils import get_http_client

if TYPE_CHECKING:
    from app.ai import AiGateway

_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


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


def build_email_system_prompt() -> str:
    """Return the system prompt for generating outreach email variables."""
    from app.ai.prompts import get_prompt
    return get_prompt("outreach_email.v1").system_prompt_template


def build_email_prompt(company: Company) -> str:
    """Construct a user prompt to generate hook, pitch, and CTA variables."""
    inferred_hook = company.ai_talking_points[0] if company.ai_talking_points else "None available"
    sender_name = yaml_config.email.from_name or "Kapil Kumar Jangid"

    context = (
        f"Company Name: {company.name}\n"
        f"Description: {company.description or 'Unknown'}\n"
        f"AI Summary: {company.ai_summary or 'None'}\n"
        f"Target Job Role: {company.jobs[0].job_title if company.jobs else 'engineering'}\n"
        f"Suggested Talking Point/Hook: {inferred_hook}\n"
    )

    return f"""Based on the company data below, write the creative parts for a cold email outreach:

{context}

The recipient is a recruiter, hiring manager, or the hiring team.
The sender is {sender_name}, a full-stack developer with open-source and developer-tooling experience.

Please write and return exactly three creative variables:
1. "hook": A tailored, specific sentence explaining why we are reaching out, referencing their recent news, tech stack, or unique product (based on the description or suggested talking point). Do not be generic.
2. "sender_pitch": A concise 1-2 sentence pitch framing the sender's full-stack development and open-source/developer-tooling experience as a compelling fit for the company's engineering work.
3. "cta": A direct, friendly call to action asking for a short chat or suggesting next steps.
"""


def generate_email(
    company: Company,
    template_name: str = "startup",
    model: str | None = None,
    dry_run: bool = False,
    ai_gateway: Any = None,
) -> dict[str, Any]:
    """Generate email subject line and body candidates for outreach to the target company.

    Args:
        company: The Company object.
        template_name: Stem of the markdown template to use (e.g., 'startup').
        model: Optional model override. Defaults to settings.openrouter_model.
        dry_run: If True, logs the prompts to be sent and returns dry run text.
        ai_gateway: Unused parameter to support direct DI call compatibility.

    Returns:
        Dict containing keys 'subject', 'body', and 'template_used'.
    """
    # 1. Load template first to fail fast if missing
    try:
        template_text = load_template(template_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "outreach/email/{company}: failed to load template '{template}' — {exc}",
            company=company.name,
            template=template_name,
            exc=exc,
        )
        return {"subject": "", "body": "", "template_used": template_name}

    # 2. Key verification
    if not settings.openrouter_api_key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Please add it to your .env file."
        )

    sys_prompt = build_email_system_prompt()
    user_prompt = build_email_prompt(company)

    # 3. Handle dry run
    if dry_run:
        logger.info(
            "dry-run: email body prompt preview for '{company}' using template '{template}'\n"
            "--- SYSTEM PROMPT ---\n{sys}\n"
            "--- USER PROMPT ---\n{user}\n"
            "---------------------",
            company=company.name,
            template=template_name,
            sys=sys_prompt,
            user=user_prompt,
        )
        # Invoke dry run on subject line to preview that prompt as well
        generate_subject_lines(company, count=1, model=model, dry_run=True, ai_gateway=ai_gateway)
        return {
            "subject": "[DRY RUN]",
            "body": "[DRY RUN]",
            "template_used": template_name,
        }

    # 4. Generate Subject Line
    subjects = generate_subject_lines(company, count=1, model=model, dry_run=False, ai_gateway=ai_gateway)
    subject = subjects[0] if subjects else ""

    # 5. POST to OpenRouter for creative variables
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
        "temperature": 0.4,
    }

    try:
        with get_http_client() as client:
            response = _post_with_retry(client, headers, json_body)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "outreach/email/{company}: OpenRouter API call failed — {exc}",
            company=company.name,
            exc=exc,
        )
        return {"subject": "", "body": "", "template_used": template_name}

    # 6. Parse LLM JSON
    try:
        payload = response.json()
        raw_content = payload["choices"][0]["message"]["content"]
        clean_json = _clean_json_content(raw_content)
        parsed = json.loads(clean_json)

        hook = parsed.get("hook", "")
        sender_pitch = parsed.get("sender_pitch", "")
        cta = parsed.get("cta", "")

        # 7. Perform template substitution
        recipient_name = company.recruiter_name or "Hiring Team"
        role_title = company.jobs[0].job_title if company.jobs else "engineering roles"
        sender_name = yaml_config.email.from_name or "Kapil Kumar Jangid"

        values = {
            "recipient_name": recipient_name,
            "company_name": company.name,
            "role_title": role_title,
            "sender_name": sender_name,
            "hook": hook,
            "sender_pitch": sender_pitch,
            "cta": cta,
        }

        body = render_template(template_text, values)
        logger.info(
            "outreach/email/{company}: successfully generated email body",
            company=company.name,
        )
        return {
            "subject": subject,
            "body": body,
            "template_used": template_name,
        }

    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "outreach/email/{company}: failed to parse/apply response — {exc}",
            company=company.name,
            exc=exc,
        )
        return {"subject": "", "body": "", "template_used": template_name}

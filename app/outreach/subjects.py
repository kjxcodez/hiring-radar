"""AI-powered subject line generator for cold email outreach using AI Gateway."""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from app.models import Company

if TYPE_CHECKING:
    from app.ai import AiGateway


def build_subject_system_prompt() -> str:
    """Return the system prompt for generating email subject lines."""
    from app.ai.prompts import get_prompt
    return get_prompt("outreach_subject.v1").system_prompt_template


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


def generate_subject_lines(
    company: Company,
    count: int = 10,
    model: str | None = None,
    dry_run: bool = False,
    ai_gateway: AiGateway | None = None,
) -> list[str]:
    """Generate multiple distinct subject line candidates for outreach to the target company.

    Args:
        company: The Company object containing data.
        count: Number of candidate subject lines to produce.
        model: Optional model override.
        dry_run: If True, logs the prompts to be sent and returns an empty list.
        ai_gateway: Optional AI Gateway instance.

    Returns:
        List of generated subject line strings, or empty list on failure.
    """
    # 1. Build prompts
    sys_prompt = build_subject_system_prompt()
    user_prompt = build_subject_prompt(company, count)

    # 2. Handle dry run
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

    # 3. Resolve ai_gateway
    if ai_gateway is None:
        from app.cli.common import get_container
        ai_gateway = get_container().ai_gateway

    try:
        # 4. Perform complete_json call
        parsed = ai_gateway.complete_json(
            prompt_id="outreach_subject.v1",
            user_content=user_prompt,
            model=model,
            temperature=0.5,
            use_cache=True,
        )

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
            "outreach/subjects/{company}: failed to generate subject lines — {exc}",
            company=company.name,
            exc=exc,
        )
        return []

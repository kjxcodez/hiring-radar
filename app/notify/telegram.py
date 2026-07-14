"""Telegram notification client and alert formatter for hiring-radar.

Interacts directly with Telegram's sendMessage Bot API using httpx.
"""

from __future__ import annotations

import httpx
from loguru import logger

from app.config import settings, yaml_config
from app.models import Company
from app.utils import get_http_client


def send_telegram_message(text: str, parse_mode: str = "Markdown") -> bool:
    """Send a text message to the configured Telegram chat.

    Splits the message into multiple sequential deliveries if it exceeds the
    4096-character limit.

    Args:
        text: Message string to send.
        parse_mode: Parsing mode for formatting ("Markdown" or "HTML").

    Returns:
        True if all message chunks were delivered successfully, False otherwise.
    """
    bot_token = settings.telegram_bot_token
    chat_id = yaml_config.telegram.chat_id

    # 1. Config validation checks
    if not bot_token or not chat_id:
        logger.warning(
            "Telegram not configured — set TELEGRAM_BOT_TOKEN in .env and "
            "telegram.chat_id in config.yaml"
        )
        return False

    if not yaml_config.telegram.enabled:
        logger.info("Telegram notifications disabled in config.yaml")
        return False

    # 2. Text splitting helper (4096 character limit)
    # We use a safe chunk limit of 4000 characters to prevent overflow issues.
    limit = 4000
    chunks = []
    current_chunk = []
    current_len = 0

    for line in text.splitlines(keepends=True):
        if current_len + len(line) > limit:
            chunks.append("".join(current_chunk))
            current_chunk = [line]
            current_len = len(line)
        else:
            current_chunk.append(line)
            current_len += len(line)
    if current_chunk:
        chunks.append("".join(current_chunk))

    # 3. HTTP Delivery
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    headers = {"Content-Type": "application/json"}
    all_success = True

    with get_http_client() as client:
        for chunk in chunks:
            payload = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": parse_mode,
            }
            try:
                resp = client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "Telegram sendMessage failed with HTTP {status}: {body}",
                    status=exc.response.status_code,
                    body=exc.response.text,
                )
                all_success = False
            except Exception as exc:  # noqa: BLE001
                logger.warning("Telegram sendMessage request failed — {exc}", exc=exc)
                all_success = False

    return all_success


def format_new_company_alert(company: Company) -> str:
    """Build a structured Markdown-formatted Telegram alert message for a company.

    Conforms to the requirements:
    - Lists location, title, jobs extra count.
    - Resolves platform or source, and adds tags dynamically.
    """
    first_job = company.jobs[0] if company.jobs else None
    
    # Resolve location
    if first_job:
        location = "Remote" if first_job.remote_type == "remote" else (first_job.location or "Unknown")
        role_title = first_job.job_title
        extra_count = len(company.jobs) - 1
        jobs_extra = f" (+{extra_count} more)" if extra_count > 0 else ""
        job_url = first_job.job_url
        platform_or_source = company.ats_platform or first_job.source
    else:
        location = "Remote" if getattr(company, "notes", None) and any("remote" in n.lower() for n in company.notes) else "Unknown"
        role_title = "Active Hiring"
        jobs_extra = ""
        job_url = company.career_page_url or company.website or "n/a"
        platform_or_source = company.ats_platform or "feed"

    website_url = company.website or company.domain or "n/a"

    # Compile talking points list (up to 3 points)
    stack_section = ""
    if company.ai_talking_points:
        points = "\n".join(f"- {p}" for p in company.ai_talking_points[:3])
        stack_section = f"Stack:\n{points}\n\n"

    # Assemble tags
    tags = []
    if first_job and first_job.remote_type == "remote":
        tags.append("#remote")
    clean_tag = "".join(c for c in platform_or_source.lower() if c.isalnum())
    if clean_tag:
        tags.append(f"#{clean_tag}")
    tag_line = " ".join(tags)

    return (
        f"🚨 *New Hiring Company*\n\n"
        f"🏢 {company.name}\n"
        f"📍 {location}\n"
        f"💼 {role_title}{jobs_extra}\n\n"
        f"🌐 {website_url}\n"
        f"📄 {job_url}\n\n"
        f"{stack_section}"
        f"{tag_line}"
    ).strip()

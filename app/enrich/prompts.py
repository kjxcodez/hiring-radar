"""Prompt templates for AI enrichment of company data.

These prompts instruct an LLM to generate structured JSON summaries and outreach hooks
based on scraped company metadata and job postings. No API calls are made from this file.
"""

from __future__ import annotations

from app.models import Company


def build_system_prompt() -> str:
    """Return the system prompt establishing the assistant's role and constraints."""
    return (
        "You are an assistant helping prepare accurate, factual, and non-hyperbolic "
        "research notes for professional cold outreach. Do not invent or assume any facts "
        "not present in or directly supported by the provided company data. If information "
        "is sparse, be honest about it. Avoid generic marketing jargon (like 'revolutionizing', "
        "'disrupting', 'game-changing') and write in a professional, direct tone."
    )


def build_enrichment_prompt(company: Company) -> str:
    """Build a prompt string incorporating all available company metadata and job postings.

    Args:
        company: The Company object containing data collected during discovery and scraping.

    Returns:
        A detailed prompt string instructing the model to return structured JSON.
    """
    # Build list of active job titles
    jobs_summary = "\n".join(
        f"- {j.job_title} ({j.location or 'unknown location'}, source: {j.source})"
        for j in company.jobs
    ) or "No jobs listed"

    # Compile all notes into a string
    notes_str = "; ".join(company.notes) if company.notes else "None"

    # Assemble company details
    company_data = (
        f"Company Name: {company.name}\n"
        f"Domain: {company.domain or 'Unknown'}\n"
        f"Website: {company.website or 'Unknown'}\n"
        f"ATS Platform: {company.ats_platform or 'Unknown'}\n"
        f"Industry: {company.industry or 'Unknown'}\n"
        f"Company Size: {company.company_size or 'Unknown'}\n"
        f"Founded Year: {company.founded_year or 'Unknown'}\n"
        f"Scrape/Enrich Notes: {notes_str}\n"
        f"Scraped Description: {company.description or 'Unknown'}\n\n"
        f"Active Job Listings:\n{jobs_summary}"
    )

    return f"""Based on the following company data, generate structured research notes:

{company_data}

You must return a valid JSON object with exactly the following three keys, formatted as raw JSON without markdown formatting, fences (no ```json or ```), or preamble:

{{
  "summary": "A 2-3 sentence overview of what the company does, their primary product or service, and their business model.",
  "talking_points": [
    "A list of 3-5 short, specific, bullet-style strings useful as cold-email hooks. Each point must reference a concrete aspect of their business, stack, or active roles, avoiding generic platitudes."
  ],
  "fit_rationale": "A 1-2 sentence framing of why a full-stack developer with open-source and developer-tooling experience might be a relevant fit for them. Be honest and conservative; if there is no clear connection, state that based on the available data."
}}
"""

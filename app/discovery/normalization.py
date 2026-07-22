"""Company and job normalization pipeline for the discovery engine.

Centralises all conversion logic that was previously duplicated across every
provider module:

- Company name cleaning (slug → title case)
- ``ats_platform`` and ``ats_slug`` assignment
- ``discovered_at`` / ``last_updated`` timestamp stamping
- ``remote_type`` inference from location strings

Usage::

    normalizer = CompanyNormalizer()
    company = normalizer.from_slug(
        slug="acmecorp",
        jobs=mapped_jobs,
        provider_name="greenhouse",
    )
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from loguru import logger

from app.models import Company, JobPosting


# ---------------------------------------------------------------------------
# Remote-type inference
# ---------------------------------------------------------------------------

#: Explicit keyword → remote_type mapping used by providers that expose a
#: ``workplaceType`` or ``telecommuting`` field.
_EXPLICIT_REMOTE_MAP: dict[str, str] = {
    "remote":   "remote",
    "hybrid":   "hybrid",
    "onsite":   "onsite",
    "on-site":  "onsite",
    "office":   "onsite",
    "in-office": "onsite",
}


def infer_remote_type(
    location: str | None = None,
    explicit_type: str | None = None,
    is_remote_flag: bool | None = None,
) -> str:
    """Resolve our ``remote_type`` Literal from provider-specific fields.

    Priority:
    1. ``is_remote_flag`` (Ashby ``isRemote``, Workable ``telecommuting``)
    2. ``explicit_type`` (Lever ``workplaceType``)
    3. Location-string heuristic (all providers)
    4. ``"unknown"`` as the safe fallback.

    Args:
        location:      Location string from the job posting.
        explicit_type: Explicit workplace type string from the provider.
        is_remote_flag: Boolean remote flag from the provider.

    Returns:
        One of ``"remote"``, ``"hybrid"``, ``"onsite"``, ``"unknown"``.
    """
    if is_remote_flag is True:
        return "remote"
    if is_remote_flag is False and explicit_type is None:
        # Not remote, but no finer classification — fall through to heuristics
        pass

    if explicit_type:
        mapped = _EXPLICIT_REMOTE_MAP.get(explicit_type.lower().strip())
        if mapped:
            return mapped

    if location and "remote" in location.lower():
        return "remote"

    return "unknown"


# ---------------------------------------------------------------------------
# Company normalizer
# ---------------------------------------------------------------------------

class CompanyNormalizer:
    """Converts raw provider data into the canonical :class:`~app.models.Company` model.

    All provider adapters delegate company construction here so that name
    cleaning, timestamp stamping, and ATS metadata assignment are applied
    consistently regardless of the source.
    """

    @staticmethod
    def clean_name(slug: str) -> str:
        """Convert an ATS slug into a human-readable company name.

        Examples:
            ``"acme-corp"`` → ``"Acme Corp"``
            ``"linear"``    → ``"Linear"``
        """
        return slug.replace("-", " ").replace("_", " ").strip().title()

    @staticmethod
    def from_slug(
        slug: str,
        jobs: list[JobPosting],
        provider_name: str,
        *,
        display_name: str | None = None,
        website: str | None = None,
        career_page_url: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Company:
        """Build a :class:`~app.models.Company` from a provider slug + job list.

        Args:
            slug:           The ATS company identifier.
            jobs:           Mapped job postings for this company.
            provider_name:  Name of the providing ATS (e.g. ``"greenhouse"``).
            display_name:   Override for the company name.  Defaults to a
                            title-cased version of ``slug``.
            website:        Known website URL if available from the API response.
            career_page_url: Known careers page URL.
            extra:          Additional fields to merge into the Company model.

        Returns:
            A fully constructed :class:`~app.models.Company` with all
            discovery metadata set.
        """
        now = datetime.now()
        name = display_name or CompanyNormalizer.clean_name(slug)
        fields: dict[str, Any] = {
            "name": name,
            "ats_platform": provider_name,
            "ats_slug": slug,
            "jobs": jobs,
            "discovered_at": now,
            "last_updated": now,
        }
        if website:
            fields["website"] = website
        if career_page_url:
            fields["career_page_url"] = career_page_url
        if extra:
            # Only merge fields that exist on the Company model
            valid_keys = Company.model_fields.keys()
            for k, v in extra.items():
                if k in valid_keys and k not in fields:
                    fields[k] = v

        return Company(**fields)

    @staticmethod
    def from_name(
        company_name: str,
        jobs: list[JobPosting],
        provider_name: str,
    ) -> Company:
        """Build a :class:`~app.models.Company` from a human-readable name.

        Used by feed-based providers (RemoteOK, WWR) that don't have slugs.
        """
        now = datetime.now()
        return Company(
            name=company_name.strip(),
            ats_platform=None,   # Feed-based — not an ATS
            ats_slug=None,
            jobs=jobs,
            discovered_at=now,
            last_updated=now,
        )

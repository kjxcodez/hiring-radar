"""Company deduplication engine for the discovery pipeline.

Merges incoming companies from multiple providers with each other and with
the existing database, using a priority-ordered key strategy to identify
duplicates.

Merge priority (descending):
1. ``ats_slug + ats_platform``   — most specific (same ATS record)
2. ``domain``                     — authoritative identity
3. ``website`` URL (normalised)  — common alternative
4. ``name.lower().strip()``      — final fallback (fuzzy, but better than nothing)

Usage::

    deduplicator = Deduplicator()
    merged, new_count, updated_count = deduplicator.merge(incoming, existing)
"""

from __future__ import annotations

from urllib.parse import urlparse

from loguru import logger

from app.models import Company


def _ats_key(company: Company) -> str | None:
    """Return a composite ATS key if both slug and platform are present."""
    if company.ats_platform and company.ats_slug:
        return f"{company.ats_platform}::{company.ats_slug}"
    return None


def _domain_key(company: Company) -> str | None:
    """Return normalised domain if set."""
    if company.domain:
        return company.domain.lower().strip()
    return None


def _website_key(company: Company) -> str | None:
    """Return normalised hostname from website URL if set."""
    if company.website:
        try:
            parsed = urlparse(company.website)
            host = (parsed.netloc or parsed.path).lower().strip()
            host = host.removeprefix("www.")
            return host if host else None
        except Exception:
            return None
    return None


def _name_key(company: Company) -> str:
    """Return normalised company name (always non-None)."""
    return company.name.lower().strip()


def _best_key(company: Company) -> str:
    """Return the highest-priority dedupe key for *company*."""
    return (
        _ats_key(company)
        or _domain_key(company)
        or _website_key(company)
        or _name_key(company)
    )


class Deduplicator:
    """Merges company lists using a priority-ordered key strategy.

    This class does **not** handle persistence — callers are responsible for
    saving the result.  It operates purely on in-memory lists.
    """

    def merge(
        self,
        incoming: list[Company],
        existing: list[Company],
    ) -> tuple[list[Company], int, int]:
        """Merge *incoming* companies into *existing* and return the result.

        When a duplicate is detected:
        - New job postings (by URL) are appended to the existing record.
        - ``last_updated`` is refreshed to the incoming value.
        - All other existing fields are preserved (no overwrite).

        Args:
            incoming: Freshly-discovered companies from providers.
            existing: Companies already stored in the repository.

        Returns:
            A 3-tuple of:
            - ``merged``: The full merged company list.
            - ``new_count``: Number of brand-new companies added.
            - ``updated_count``: Number of existing companies whose job list
              was updated with new postings.
        """
        # Build index from all existing companies
        index: dict[str, Company] = {}
        for co in existing:
            key = _best_key(co)
            if key not in index:
                index[key] = co

        new_count = 0
        updated_count = 0

        for new_co in incoming:
            key = _best_key(new_co)

            if key in index:
                existing_co = index[key]
                existing_urls = {j.job_url for j in existing_co.jobs}
                added = [j for j in new_co.jobs if j.job_url not in existing_urls]

                if added:
                    existing_co.jobs.extend(added)
                    existing_co.last_updated = new_co.last_updated
                    updated_count += 1
                    logger.debug(
                        "deduplication: updated '{name}' with {n} new job(s)",
                        name=existing_co.name,
                        n=len(added),
                    )
            else:
                index[key] = new_co
                new_count += 1
                logger.debug(
                    "deduplication: added new company '{name}'",
                    name=new_co.name,
                )

        merged = list(index.values())
        logger.info(
            "deduplication: {total} total, {new} new, {upd} updated",
            total=len(merged),
            new=new_count,
            upd=updated_count,
        )
        return merged, new_count, updated_count

    def dedupe_incoming(self, incoming: list[Company]) -> list[Company]:
        """Deduplicate *incoming* against itself (cross-provider merging).

        Run this before merging with the repository to collapse companies that
        appear in multiple providers (e.g. Greenhouse + Lever for the same co).

        Returns:
            A deduplicated list of companies with merged job lists.
        """
        merged, _, _ = self.merge(incoming, [])
        return merged

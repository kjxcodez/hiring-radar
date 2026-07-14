"""Lever public postings API discovery module.

Lever gives every company a public, unauthenticated JSON endpoint:

    https://api.lever.co/v0/postings/{company_slug}?mode=json

The ``company_slug`` is the short identifier found in a company's Lever
job board URL — e.g. ``jobs.lever.co/acmecorp`` → slug is ``acmecorp``.
You can find it by visiting a company's careers page and looking at the
``jobs.lever.co`` or ``hire.lever.co`` URL, or from the canonical link
embedded in their careers-page HTML.

Unlike Greenhouse, Lever returns a **JSON array** directly (no wrapping
object).  Each posting includes ``workplaceType`` which may already carry
an explicit ``"remote"``, ``"hybrid"``, or ``"onsite"`` value — this is
used directly when present, falling back to a location-string heuristic
for older postings that predate the field.

This module exposes a single entry-point:

    from app.discover.lever import discover
    companies = discover(["acmecorp", "stripe", "notion"])
"""

from __future__ import annotations

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

from app.models import Company, JobPosting
from app.utils import RateLimiter, get_http_client

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL = "https://api.lever.co/v0/postings/{slug}?mode=json"

# Lever's workplaceType values → our remote_type Literal
_WORKPLACE_MAP: dict[str, str] = {
    "remote": "remote",
    "hybrid": "hybrid",
    "onsite": "onsite",
    "on-site": "onsite",
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _infer_remote_type(workplace_type: str | None, location: str | None) -> str:
    """Resolve our ``remote_type`` Literal from Lever's fields.

    Priority:
    1. ``workplaceType`` — Lever's explicit field (used when present).
    2. Location-string heuristic — same as the Greenhouse module.
    3. ``"unknown"`` as the safe fallback.
    """
    if workplace_type:
        mapped = _WORKPLACE_MAP.get(workplace_type.lower().strip())
        if mapped:
            return mapped

    if location and "remote" in location.lower():
        return "remote"

    return "unknown"


def _map_job(raw: dict, slug: str) -> JobPosting | None:
    """Convert a raw Lever posting dict into a JobPosting.

    Returns ``None`` if the minimum required fields are missing.
    """
    title: str | None = raw.get("text")
    url: str | None = raw.get("hostedUrl")
    if not title or not url:
        logger.debug(
            "lever/{slug}: skipping posting with missing title or URL — {raw}",
            slug=slug,
            raw=raw,
        )
        return None

    categories: dict = raw.get("categories") or {}
    location: str | None = categories.get("location")
    workplace_type: str | None = raw.get("workplaceType")

    return JobPosting(
        job_title=title,
        job_url=url,
        location=location,
        remote_type=_infer_remote_type(workplace_type, location),  # type: ignore[arg-type]
        source="lever",
    )


# ---------------------------------------------------------------------------
# Retry-wrapped HTTP fetch (transient errors only, not 404)
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),  # 1 initial + 2 retries
    reraise=True,
)
def _fetch_with_retry(client: httpx.Client, url: str) -> httpx.Response:
    """GET *url*, retrying on transient network/timeout errors (max 2 retries).

    Raises immediately on HTTP errors (e.g. 404 invalid slug) —
    those are not retryable.
    """
    resp = client.get(url)
    resp.raise_for_status()
    return resp


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def discover(company_slugs: list[str]) -> list[Company]:
    """Discover hiring companies via the Lever public postings API.

    Fetches job postings for each *company_slug*, maps them to
    :class:`~app.models.JobPosting` objects, and returns one
    :class:`~app.models.Company` per slug that has at least one posting.

    Slugs with no postings, invalid slugs (404), or persistent network
    failures are skipped with a warning — they never crash the batch.

    Args:
        company_slugs: List of Lever company slugs, e.g. ``["stripe", "notion"]``.

    Returns:
        List of :class:`~app.models.Company` objects, one per slug with jobs.
    """
    results: list[Company] = []
    rate_limiter = RateLimiter()

    with get_http_client() as client:
        for slug in company_slugs:
            url = _BASE_URL.format(slug=slug)
            logger.info("lever: fetching {url}", url=url)

            # --- Fetch with retry on transient errors ---
            try:
                response = _fetch_with_retry(client, url)
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "lever/{slug}: HTTP {status} — skipping (invalid slug?)",
                    slug=slug,
                    status=exc.response.status_code,
                )
                continue
            except (httpx.TimeoutException, httpx.ConnectError, RetryError) as exc:
                logger.warning(
                    "lever/{slug}: network error after retries — {exc}",
                    slug=slug,
                    exc=exc,
                )
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "lever/{slug}: unexpected error — {exc}",
                    slug=slug,
                    exc=exc,
                )
                continue

            # Apply rate-limiter delay after the response so the first
            # request is not artificially delayed.
            rate_limiter.wait(url)

            # --- Parse (Lever returns a bare JSON array) ---
            try:
                raw_postings: list[dict] = response.json()
                if not isinstance(raw_postings, list):
                    logger.warning(
                        "lever/{slug}: unexpected response shape (not a list) — skipping",
                        slug=slug,
                    )
                    continue
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "lever/{slug}: failed to parse JSON — {exc}",
                    slug=slug,
                    exc=exc,
                )
                continue

            # --- Map postings ---
            jobs: list[JobPosting] = []
            for raw in raw_postings:
                try:
                    job = _map_job(raw, slug)
                    if job is not None:
                        jobs.append(job)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "lever/{slug}: skipping malformed posting entry — {exc}",
                        slug=slug,
                        exc=exc,
                    )

            if not jobs:
                logger.info(
                    "lever/{slug}: no postings found — skipping company",
                    slug=slug,
                )
                continue

            now = datetime.now()
            company = Company(
                name=slug.replace("-", " ").title(),
                ats_platform="lever",
                ats_slug=slug,
                jobs=jobs,
                discovered_at=now,
                last_updated=now,
            )
            logger.info(
                "lever/{slug}: found {n} posting(s)",
                slug=slug,
                n=len(jobs),
            )
            results.append(company)

    logger.info(
        "lever: discovery complete — {total} companies with jobs from {n} slugs",
        total=len(results),
        n=len(company_slugs),
    )
    return results

"""Workable public widget API discovery module.

Workable gives every company a public, unauthenticated JSON endpoint:

    https://apply.workable.com/api/v1/widget/accounts/{account_subdomain}

The ``account_subdomain`` is the slug found in a company's Workable job
board URL — e.g. ``apply.workable.com/acmecorp`` → subdomain is
``acmecorp``.  You can find it by visiting a company's careers page and
looking for ``workable.com`` or ``apply.workable.com`` in the URL, or by
inspecting network requests from their embedded job-board widget.

The response is a JSON object with a top-level ``jobs`` array.  Each job
includes:

- ``title``           — job title string
- ``url``             — canonical job posting URL
- ``location``        — object with ``city``, ``country``, ``region``,
                        ``telecommute`` (bool, sometimes present here too)
- ``telecommuting``   — top-level boolean flag; ``True`` means fully remote

``telecommuting: True`` maps directly to ``remote_type="remote"``.  When
``False`` or absent the location-string heuristic applies, consistent with
other discover modules.

This module exposes a single entry-point::

    from app.discover.workable import discover
    companies = discover(["acmecorp", "notion", "buffer"])
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

_BASE_URL = "https://apply.workable.com/api/v1/widget/accounts/{subdomain}"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _infer_remote_type(telecommuting: bool | None, location: dict | None) -> str:
    """Resolve our ``remote_type`` Literal from Workable's fields.

    Priority:
    1. Top-level ``telecommuting`` boolean — used when present.
    2. ``location.telecommute`` sub-field — some older postings use this.
    3. Location-string heuristic — concatenate city/region/country and
       check for "remote" (case-insensitive).
    4. ``"unknown"`` as the safe fallback.
    """
    if telecommuting is True:
        return "remote"

    loc = location or {}

    # Some postings put the flag in the nested location object instead.
    if loc.get("telecommute") is True:
        return "remote"

    # Concatenate available location parts for the string heuristic.
    loc_str = " ".join(
        filter(None, [loc.get("city"), loc.get("region"), loc.get("country")])
    )
    if loc_str and "remote" in loc_str.lower():
        return "remote"

    return "unknown"


def _map_job(raw: dict, subdomain: str) -> JobPosting | None:
    """Convert a raw Workable job dict into a JobPosting.

    Returns ``None`` if the minimum required fields are missing.
    """
    title: str | None = raw.get("title")
    url: str | None = raw.get("url")
    if not title or not url:
        logger.debug(
            "workable/{subdomain}: skipping job with missing title or URL — {raw}",
            subdomain=subdomain,
            raw=raw,
        )
        return None

    location: dict | None = raw.get("location") or None
    telecommuting: bool | None = raw.get("telecommuting")

    # Build a human-readable location string from the nested location object.
    location_str: str | None = None
    if isinstance(location, dict):
        parts = filter(None, [location.get("city"), location.get("region"), location.get("country")])
        joined = ", ".join(parts)
        location_str = joined or None

    return JobPosting(
        job_title=title,
        job_url=url,
        location=location_str,
        remote_type=_infer_remote_type(telecommuting, location if isinstance(location, dict) else None),  # type: ignore[arg-type]
        source="workable",
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

    Raises immediately on HTTP errors (e.g. 404 invalid subdomain) —
    those are not retryable.
    """
    resp = client.get(url)
    resp.raise_for_status()
    return resp


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def discover(account_subdomains: list[str]) -> list[Company]:
    """Discover hiring companies via the Workable public widget API.

    Fetches job listings for each *account_subdomain*, maps them to
    :class:`~app.models.JobPosting` objects, and returns one
    :class:`~app.models.Company` per subdomain that has at least one job.

    Subdomains with no jobs, invalid subdomains (404), or persistent network
    failures are skipped with a warning — they never crash the batch.

    Args:
        account_subdomains: List of Workable account slugs, e.g.
            ``["notion", "buffer"]``.

    Returns:
        List of :class:`~app.models.Company` objects, one per subdomain
        with jobs.
    """
    results: list[Company] = []
    rate_limiter = RateLimiter()

    with get_http_client() as client:
        for subdomain in account_subdomains:
            url = _BASE_URL.format(subdomain=subdomain)
            logger.info("workable: fetching {url}", url=url)

            # --- Fetch with retry on transient errors ---
            try:
                response = _fetch_with_retry(client, url)
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "workable/{subdomain}: HTTP {status} — skipping (invalid subdomain?)",
                    subdomain=subdomain,
                    status=exc.response.status_code,
                )
                continue
            except (httpx.TimeoutException, httpx.ConnectError, RetryError) as exc:
                logger.warning(
                    "workable/{subdomain}: network error after retries — {exc}",
                    subdomain=subdomain,
                    exc=exc,
                )
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "workable/{subdomain}: unexpected error — {exc}",
                    subdomain=subdomain,
                    exc=exc,
                )
                continue

            # Apply rate-limiter delay after the response so the first
            # request is not artificially delayed.
            rate_limiter.wait(url)

            # --- Parse ---
            try:
                payload: dict = response.json()
                raw_jobs: list[dict] = payload.get("jobs") or []
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "workable/{subdomain}: failed to parse JSON — {exc}",
                    subdomain=subdomain,
                    exc=exc,
                )
                continue

            # --- Map jobs ---
            jobs: list[JobPosting] = []
            for raw in raw_jobs:
                try:
                    job = _map_job(raw, subdomain)
                    if job is not None:
                        jobs.append(job)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "workable/{subdomain}: skipping malformed job entry — {exc}",
                        subdomain=subdomain,
                        exc=exc,
                    )

            if not jobs:
                logger.info(
                    "workable/{subdomain}: no jobs found — skipping company",
                    subdomain=subdomain,
                )
                continue

            now = datetime.now()
            company = Company(
                name=subdomain.replace("-", " ").title(),
                ats_platform="workable",
                ats_slug=subdomain,
                jobs=jobs,
                discovered_at=now,
                last_updated=now,
            )
            logger.info(
                "workable/{subdomain}: found {n} job(s)",
                subdomain=subdomain,
                n=len(jobs),
            )
            results.append(company)

    logger.info(
        "workable: discovery complete — {total} companies with jobs from {n} subdomains",
        total=len(results),
        n=len(account_subdomains),
    )
    return results

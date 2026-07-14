"""Ashby public job-board API discovery module.

Ashby gives every company a public, unauthenticated JSON endpoint:

    https://api.ashbyhq.com/posting-api/job-board/{job_board_name}

The ``job_board_name`` is the slug found in a company's Ashby job board
URL — e.g. ``jobs.ashbyhq.com/acmecorp`` → name is ``acmecorp``.
You can find it by visiting a company's careers page and inspecting the
``ashbyhq.com`` URL, or from the network tab when the job board widget
loads.

The response is a JSON object with a top-level ``jobs`` array.  Each job
includes:

- ``title``          — job title string
- ``jobUrl``         — canonical job posting URL (preferred)
- ``applyUrl``       — fallback URL when ``jobUrl`` is absent
- ``location``       — location string (may be ``None``)
- ``employmentType`` — e.g. ``"FullTime"``, ``"PartTime"`` (not used for
  remote_type but recorded as a future enrichment hook)
- ``isRemote``       — boolean when present; used directly for
  ``remote_type``; falls back to the location-string heuristic when absent

This module exposes a single entry-point::

    from app.discover.ashby import discover
    companies = discover(["acmecorp", "linear", "retool"])
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

_BASE_URL = "https://api.ashbyhq.com/posting-api/job-board/{name}"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _infer_remote_type(is_remote: bool | None, location: str | None) -> str:
    """Resolve our ``remote_type`` Literal from Ashby's fields.

    Priority:
    1. ``isRemote`` boolean — Ashby's explicit flag (used when present).
    2. Location-string heuristic — same convention as greenhouse/lever.
    3. ``"unknown"`` as the safe fallback.
    """
    if is_remote is True:
        return "remote"
    if is_remote is False:
        return "onsite"
    # isRemote absent — fall back to location string
    if location and "remote" in location.lower():
        return "remote"
    return "unknown"


def _map_job(raw: dict, name: str) -> JobPosting | None:
    """Convert a raw Ashby job dict into a JobPosting.

    Returns ``None`` if the minimum required fields are missing.
    """
    title: str | None = raw.get("title")
    url: str | None = raw.get("jobUrl") or raw.get("applyUrl")
    if not title or not url:
        logger.debug(
            "ashby/{name}: skipping job with missing title or URL — {raw}",
            name=name,
            raw=raw,
        )
        return None

    location: str | None = raw.get("location") or None
    is_remote: bool | None = raw.get("isRemote")  # may be absent → None

    return JobPosting(
        job_title=title,
        job_url=url,
        location=location,
        remote_type=_infer_remote_type(is_remote, location),  # type: ignore[arg-type]
        source="ashby",
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

    Raises immediately on HTTP errors (e.g. 404 invalid board name) —
    those are not retryable.
    """
    resp = client.get(url)
    resp.raise_for_status()
    return resp


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def discover(job_board_names: list[str]) -> list[Company]:
    """Discover hiring companies via the Ashby public job-board API.

    Fetches job listings for each *job_board_name*, maps them to
    :class:`~app.models.JobPosting` objects, and returns one
    :class:`~app.models.Company` per name that has at least one job.

    Names with no jobs, invalid names (404), or persistent network
    failures are skipped with a warning — they never crash the batch.

    Args:
        job_board_names: List of Ashby job-board slugs, e.g.
            ``["linear", "retool"]``.

    Returns:
        List of :class:`~app.models.Company` objects, one per name with jobs.
    """
    results: list[Company] = []
    rate_limiter = RateLimiter()

    with get_http_client() as client:
        for name in job_board_names:
            url = _BASE_URL.format(name=name)
            logger.info("ashby: fetching {url}", url=url)

            # --- Fetch with retry on transient errors ---
            try:
                response = _fetch_with_retry(client, url)
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "ashby/{name}: HTTP {status} — skipping (invalid board name?)",
                    name=name,
                    status=exc.response.status_code,
                )
                continue
            except (httpx.TimeoutException, httpx.ConnectError, RetryError) as exc:
                logger.warning(
                    "ashby/{name}: network error after retries — {exc}",
                    name=name,
                    exc=exc,
                )
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "ashby/{name}: unexpected error — {exc}",
                    name=name,
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
                    "ashby/{name}: failed to parse JSON — {exc}",
                    name=name,
                    exc=exc,
                )
                continue

            # --- Map jobs ---
            jobs: list[JobPosting] = []
            for raw in raw_jobs:
                try:
                    job = _map_job(raw, name)
                    if job is not None:
                        jobs.append(job)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "ashby/{name}: skipping malformed job entry — {exc}",
                        name=name,
                        exc=exc,
                    )

            if not jobs:
                logger.info(
                    "ashby/{name}: no jobs found — skipping company",
                    name=name,
                )
                continue

            now = datetime.now()
            company = Company(
                name=name.replace("-", " ").title(),
                ats_platform="ashby",
                ats_slug=name,
                jobs=jobs,
                discovered_at=now,
                last_updated=now,
            )
            logger.info(
                "ashby/{name}: found {n} job(s)",
                name=name,
                n=len(jobs),
            )
            results.append(company)

    logger.info(
        "ashby: discovery complete — {total} companies with jobs from {n} names",
        total=len(results),
        n=len(job_board_names),
    )
    return results

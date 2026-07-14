"""BambooHR public job listing API discovery module.

BambooHR exposes a per-company public endpoint (no authentication needed):

    https://{company_subdomain}.bamboohr.com/careers/list

The ``company_subdomain`` is the slug found in a company's BambooHR careers
page URL — e.g. ``acmecorp.bamboohr.com/careers`` → subdomain is
``acmecorp``.

The response is a JSON object with a top-level ``result`` array.  Each
entry includes:

- ``title``    — job title string
- ``id``       — integer or string job ID; used to construct the apply URL:
                 ``https://{subdomain}.bamboohr.com/careers/{id}``
- ``location`` — a dict or string whose shape varies across BambooHR
                 accounts (see ``_extract_location`` for defensive handling)

BambooHR does not provide a consistent explicit remote flag, so
``remote_type`` is always inferred via the location-string heuristic
(same approach as greenhouse.py).

This module exposes a single entry-point::

    from app.discover.bamboohr import discover
    companies = discover(["acmecorp", "zapier", "buffer"])
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

_LIST_URL = "https://{subdomain}.bamboohr.com/careers/list"
_JOB_URL  = "https://{subdomain}.bamboohr.com/careers/{job_id}"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_location(raw_location: object) -> str | None:
    """Defensively extract a human-readable location string.

    BambooHR account schemas are inconsistent:
    - Some accounts return ``location`` as a plain string.
    - Some return a dict with ``city``, ``state``, ``country``.
    - Some omit it entirely (``None`` or missing key).

    Returns a stripped string or ``None`` when nothing useful is found.
    """
    if raw_location is None:
        return None
    if isinstance(raw_location, str):
        return raw_location.strip() or None
    if isinstance(raw_location, dict):
        parts = filter(None, [
            raw_location.get("city"),
            raw_location.get("state"),
            raw_location.get("country"),
        ])
        joined = ", ".join(str(p).strip() for p in parts if str(p).strip())
        return joined or None
    # Unexpected type — coerce to string as a last resort
    return str(raw_location).strip() or None


def _infer_remote_type(location: str | None) -> str:
    """Return 'remote' if the location string hints at remote work, else 'unknown'."""
    if location and "remote" in location.lower():
        return "remote"
    return "unknown"


def _map_job(raw: dict, subdomain: str) -> JobPosting | None:
    """Convert a raw BambooHR job dict into a JobPosting.

    Returns ``None`` if the minimum required fields are missing.
    """
    title: str | None = raw.get("title")
    job_id = raw.get("id")

    if not title or job_id is None:
        logger.debug(
            "bamboohr/{subdomain}: skipping entry with missing title or id — {raw}",
            subdomain=subdomain,
            raw=raw,
        )
        return None

    url = _JOB_URL.format(subdomain=subdomain, job_id=job_id)
    location = _extract_location(raw.get("location"))

    return JobPosting(
        job_title=title,
        job_url=url,
        location=location,
        remote_type=_infer_remote_type(location),  # type: ignore[arg-type]
        source="bamboohr",
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

def discover(company_subdomains: list[str]) -> list[Company]:
    """Discover hiring companies via the BambooHR public careers endpoint.

    Fetches job listings for each *company_subdomain*, maps them to
    :class:`~app.models.JobPosting` objects, and returns one
    :class:`~app.models.Company` per subdomain that has at least one job.

    Subdomains with no jobs, invalid subdomains (404), or persistent network
    failures are skipped with a warning — they never crash the batch.

    Args:
        company_subdomains: List of BambooHR company slugs, e.g.
            ``["zapier", "buffer"]``.

    Returns:
        List of :class:`~app.models.Company` objects, one per subdomain
        with jobs.
    """
    results: list[Company] = []
    rate_limiter = RateLimiter()

    with get_http_client() as client:
        for subdomain in company_subdomains:
            url = _LIST_URL.format(subdomain=subdomain)
            logger.info("bamboohr: fetching {url}", url=url)

            # --- Fetch with retry on transient errors ---
            try:
                response = _fetch_with_retry(client, url)
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "bamboohr/{subdomain}: HTTP {status} — skipping (invalid subdomain?)",
                    subdomain=subdomain,
                    status=exc.response.status_code,
                )
                continue
            except (httpx.TimeoutException, httpx.ConnectError, RetryError) as exc:
                logger.warning(
                    "bamboohr/{subdomain}: network error after retries — {exc}",
                    subdomain=subdomain,
                    exc=exc,
                )
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "bamboohr/{subdomain}: unexpected error — {exc}",
                    subdomain=subdomain,
                    exc=exc,
                )
                continue

            # Apply rate-limiter delay after the response so the first
            # request is not artificially delayed.
            rate_limiter.wait(url)

            # --- Parse (BambooHR wraps results in a "result" key) ---
            try:
                payload: dict = response.json()
                raw_jobs: list[dict] = payload.get("result") or []
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "bamboohr/{subdomain}: failed to parse JSON — {exc}",
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
                        "bamboohr/{subdomain}: skipping malformed entry — {exc}",
                        subdomain=subdomain,
                        exc=exc,
                    )

            if not jobs:
                logger.info(
                    "bamboohr/{subdomain}: no jobs found — skipping company",
                    subdomain=subdomain,
                )
                continue

            now = datetime.now()
            company = Company(
                name=subdomain.replace("-", " ").title(),
                ats_platform="bamboohr",
                ats_slug=subdomain,
                jobs=jobs,
                discovered_at=now,
                last_updated=now,
            )
            logger.info(
                "bamboohr/{subdomain}: found {n} job(s)",
                subdomain=subdomain,
                n=len(jobs),
            )
            results.append(company)

    logger.info(
        "bamboohr: discovery complete — {total} companies with jobs from {n} subdomains",
        total=len(results),
        n=len(company_subdomains),
    )
    return results

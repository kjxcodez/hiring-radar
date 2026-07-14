"""Greenhouse public board API discovery module.

Greenhouse gives every company a public, unauthenticated JSON endpoint:

    https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true

The ``board_token`` is the short slug found in a company's Greenhouse job
board URL — e.g. ``boards.greenhouse.io/acmecorp`` → token is ``acmecorp``.
You can find a company's token by visiting their careers page and inspecting
the ``boards.greenhouse.io`` URL in the network tab, or by checking the
URL embedded in their ``<link rel="canonical">`` header.

This module exposes a single entry-point:

    from app.discover.greenhouse import discover
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
from app.utils import RateLimiter, get_http_client, safe_get

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _infer_remote_type(location_name: str | None) -> str:
    """Return 'remote' if the location string hints at remote work, else 'unknown'."""
    if location_name and "remote" in location_name.lower():
        return "remote"
    return "unknown"


def _map_job(raw: dict, board_token: str) -> JobPosting | None:
    """Convert a raw Greenhouse job dict into a JobPosting.

    Returns ``None`` if the minimum required fields are missing.
    """
    title: str | None = raw.get("title")
    url: str | None = raw.get("absolute_url")
    if not title or not url:
        logger.debug(
            "greenhouse/{token}: skipping job with missing title or URL — {raw}",
            token=board_token,
            raw=raw,
        )
        return None

    location_name: str | None = (raw.get("location") or {}).get("name")

    return JobPosting(
        job_title=title,
        job_url=url,
        location=location_name,
        remote_type=_infer_remote_type(location_name),  # type: ignore[arg-type]
        source="greenhouse",
    )


# ---------------------------------------------------------------------------
# Retry-wrapped HTTP fetch (transient errors only, not 404)
# ---------------------------------------------------------------------------

def _is_transient(exc: BaseException) -> bool:
    """Return True for network/timeout errors; False for HTTP errors (incl. 404)."""
    return isinstance(exc, (httpx.TimeoutException, httpx.ConnectError))


@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),  # 1 initial + 2 retries
    reraise=True,
)
def _fetch_with_retry(client: httpx.Client, url: str) -> httpx.Response:
    """GET *url*, retrying on transient network/timeout errors (max 2 retries).

    Raises immediately on HTTP errors (e.g. 404 invalid board token) —
    those are not retryable.
    """
    resp = client.get(url)
    resp.raise_for_status()
    return resp


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def discover(board_tokens: list[str]) -> list[Company]:
    """Discover hiring companies via the Greenhouse public board API.

    Fetches job listings for each *board_token*, maps them to
    :class:`~app.models.JobPosting` objects, and returns one
    :class:`~app.models.Company` per token that has at least one job.

    Tokens with no jobs, invalid tokens (404), or persistent network
    failures are skipped with a warning — they never crash the batch.

    Args:
        board_tokens: List of Greenhouse board slugs, e.g. ``["stripe", "notion"]``.

    Returns:
        List of :class:`~app.models.Company` objects, one per token with jobs.
    """
    results: list[Company] = []
    rate_limiter = RateLimiter()

    with get_http_client() as client:
        for token in board_tokens:
            url = _BASE_URL.format(token=token)
            logger.info("greenhouse: fetching {url}", url=url)

            # --- Fetch with retry on transient errors ---
            try:
                response = _fetch_with_retry(client, url)
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "greenhouse/{token}: HTTP {status} — skipping (invalid token?)",
                    token=token,
                    status=exc.response.status_code,
                )
                continue
            except (httpx.TimeoutException, httpx.ConnectError, RetryError) as exc:
                logger.warning(
                    "greenhouse/{token}: network error after retries — {exc}",
                    token=token,
                    exc=exc,
                )
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "greenhouse/{token}: unexpected error — {exc}",
                    token=token,
                    exc=exc,
                )
                continue

            # Apply rate limiter delay *after* the response so the first
            # request is not artificially delayed.
            rate_limiter.wait(url)

            # --- Parse ---
            try:
                payload: dict = response.json()
                raw_jobs: list[dict] = payload.get("jobs") or []
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "greenhouse/{token}: failed to parse JSON — {exc}",
                    token=token,
                    exc=exc,
                )
                continue

            # --- Map jobs ---
            jobs: list[JobPosting] = []
            for raw in raw_jobs:
                try:
                    job = _map_job(raw, token)
                    if job is not None:
                        jobs.append(job)
                except Exception as exc:  # noqa: BLE001
                    logger.debug(
                        "greenhouse/{token}: skipping malformed job entry — {exc}",
                        token=token,
                        exc=exc,
                    )

            if not jobs:
                logger.info(
                    "greenhouse/{token}: no jobs found — skipping company",
                    token=token,
                )
                continue

            now = datetime.now()
            company = Company(
                name=token.replace("-", " ").title(),
                ats_platform="greenhouse",
                ats_slug=token,
                jobs=jobs,
                discovered_at=now,
                last_updated=now,
            )
            logger.info(
                "greenhouse/{token}: found {n} job(s)",
                token=token,
                n=len(jobs),
            )
            results.append(company)

    logger.info(
        "greenhouse: discovery complete — {total} companies with jobs from {n} tokens",
        total=len(results),
        n=len(board_tokens),
    )
    return results

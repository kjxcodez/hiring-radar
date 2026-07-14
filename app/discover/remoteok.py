"""RemoteOK public API discovery module.

RemoteOK exposes a single global feed — no per-company token needed:

    https://remoteok.com/api

The endpoint returns a JSON array where:
- Element [0] is a legal/metadata notice object (skipped by this module).
- Elements [1:] are job postings, each containing ``position``,
  ``company``, ``url``, ``location``, and ``tags``.

Because every listing on RemoteOK is remote by definition, all
JobPosting records produced here use ``remote_type="remote"`` without
any inference.  ``ats_platform`` is left unset (``None``) — RemoteOK is
a job aggregator, not an ATS.

The entire feed is fetched in a single HTTP call, so there is no
per-item rate limiting loop (unlike greenhouse.py / lever.py).
RemoteOK's own usage guidelines ask consumers to set a descriptive
User-Agent and avoid hammering the endpoint — our configured
``settings.user_agent`` satisfies this, and callers should not invoke
this module more frequently than once every few minutes.

Entry-point::

    from app.discover.remoteok import discover
    companies = discover(limit=50)
"""

from __future__ import annotations

from collections import defaultdict
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
from app.utils import get_http_client

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_API_URL = "https://remoteok.com/api"

# ---------------------------------------------------------------------------
# Retry-wrapped fetch (transient errors only)
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),  # 1 initial + 2 retries
    reraise=True,
)
def _fetch_with_retry(client: httpx.Client) -> httpx.Response:
    """GET the RemoteOK API, retrying only on transient network errors."""
    resp = client.get(_API_URL)
    resp.raise_for_status()
    return resp


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _map_job(raw: dict) -> JobPosting | None:
    """Convert a raw RemoteOK job dict into a JobPosting.

    Returns ``None`` if the minimum required fields (title, URL) are missing.
    """
    title: str | None = raw.get("position")
    url: str | None = raw.get("url")
    if not title or not url:
        logger.debug(
            "remoteok: skipping entry with missing position or URL — {raw}",
            raw=raw,
        )
        return None

    location: str | None = raw.get("location") or None

    return JobPosting(
        job_title=title,
        job_url=url,
        location=location,
        remote_type="remote",   # RemoteOK is remote-only by definition
        source="remoteok",
    )


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def discover(limit: int = 50) -> list[Company]:
    """Discover remote hiring companies from the RemoteOK global feed.

    Fetches the single RemoteOK API endpoint, skips the metadata header
    element, maps up to *limit* job postings into
    :class:`~app.models.JobPosting` objects, groups them by company name,
    and returns one :class:`~app.models.Company` per company with at least
    one job.

    Note:
        Unlike :mod:`app.discover.greenhouse` and :mod:`app.discover.lever`,
        this function takes no slug list — the API is a global feed.
        The ``limit`` parameter caps **total job postings collected**
        (not companies), so the number of Company objects returned may be
        smaller than *limit*.

    Args:
        limit: Maximum number of job postings to collect from the feed.

    Returns:
        List of :class:`~app.models.Company` objects.
    """
    # RemoteOK is a single endpoint — one HTTP call covers everything.
    # No per-domain rate-limiter loop is needed here (see module docstring).
    with get_http_client() as client:
        logger.info("remoteok: fetching {url}", url=_API_URL)
        try:
            response = _fetch_with_retry(client)
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "remoteok: HTTP {status} from API — aborting",
                status=exc.response.status_code,
            )
            return []
        except (httpx.TimeoutException, httpx.ConnectError, RetryError) as exc:
            logger.warning(
                "remoteok: network error after retries — {exc}",
                exc=exc,
            )
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning("remoteok: unexpected error — {exc}", exc=exc)
            return []

    # --- Parse feed ---
    try:
        raw_feed: list = response.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("remoteok: failed to parse JSON — {exc}", exc=exc)
        return []

    if not isinstance(raw_feed, list) or len(raw_feed) < 2:  # noqa: PLR2004
        logger.warning(
            "remoteok: unexpected response shape (got {n} elements)",
            n=len(raw_feed) if isinstance(raw_feed, list) else "non-list",
        )
        return []

    # Element [0] is always the legal/metadata notice — skip it.
    postings = raw_feed[1:]
    logger.info("remoteok: {n} raw postings in feed", n=len(postings))

    # --- Map postings, stopping once we hit the limit ---
    # Group by company name → list[JobPosting]
    by_company: dict[str, list[JobPosting]] = defaultdict(list)
    collected = 0

    for raw in postings:
        if collected >= limit:
            break
        if not isinstance(raw, dict):
            continue
        try:
            job = _map_job(raw)
            if job is None:
                continue
            company_name: str = (raw.get("company") or "Unknown").strip()
            by_company[company_name].append(job)
            collected += 1
        except Exception as exc:  # noqa: BLE001
            logger.debug(
                "remoteok: skipping malformed entry — {exc}",
                exc=exc,
            )

    logger.info(
        "remoteok: collected {jobs} job(s) across {cos} company/companies (limit={limit})",
        jobs=collected,
        cos=len(by_company),
        limit=limit,
    )

    # --- Build Company objects ---
    now = datetime.now()
    results: list[Company] = []
    for company_name, jobs in by_company.items():
        results.append(
            Company(
                name=company_name,
                ats_platform=None,   # RemoteOK is an aggregator, not an ATS
                ats_slug=None,
                jobs=jobs,
                discovered_at=now,
                last_updated=now,
            )
        )

    return results

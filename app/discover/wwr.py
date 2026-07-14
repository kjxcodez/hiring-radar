"""We Work Remotely (WWR) RSS feed discovery module.

WWR publishes per-category RSS feeds at:

    https://weworkremotely.com/categories/{category-slug}.rss

The feed URL for a given category is stable and publicly documented on
the WWR website.  Below is the v1 set of feeds we consume; additional
categories can be added to ``_FEED_URLS`` from the category listing at:
    https://weworkremotely.com/remote-jobs

Each RSS ``<item>`` contains:
- ``<title>``  — usually "Company: Job Title" (colon-separated).
- ``<link>``   — canonical job URL.
- ``<region>`` — optional custom WWR tag for location/timezone hints.

Because every listing on WWR is remote-focused, all JobPosting records
use ``remote_type="remote"`` without any inference.  ``ats_platform`` is
left ``None`` — WWR is a job board, not an ATS.

Entry-point::

    from app.discover.wwr import discover
    companies = discover(limit=50)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
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
from app.utils import RateLimiter, get_http_client

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# v1 feed set — add more from https://weworkremotely.com/remote-jobs
_FEED_URLS: list[str] = [
    "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    "https://weworkremotely.com/categories/remote-devops-sysadmin-jobs.rss",
    "https://weworkremotely.com/categories/remote-product-jobs.rss",
]

# WWR uses a custom namespace for the <region> tag.
_WWR_NS = "https://weworkremotely.com"

# ---------------------------------------------------------------------------
# Retry-wrapped fetch (transient errors only)
# ---------------------------------------------------------------------------

@retry(
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),  # 1 initial + 2 retries
    reraise=True,
)
def _fetch_with_retry(client: httpx.Client, url: str) -> httpx.Response:
    """GET *url*, retrying only on transient network errors."""
    resp = client.get(url)
    resp.raise_for_status()
    return resp


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_title(raw_title: str) -> tuple[str, str]:
    """Split a WWR title string into (company_name, job_title).

    WWR titles follow the pattern ``"Company: Job Title"``.
    If no colon is present the whole string is used as job_title and
    company_name falls back to ``"Unknown"``.
    """
    if ":" in raw_title:
        company_part, _, job_part = raw_title.partition(":")
        return company_part.strip(), job_part.strip()
    return "Unknown", raw_title.strip()


def _parse_feed(xml_text: str, feed_url: str) -> list[tuple[str, JobPosting]]:
    """Parse an RSS feed and return a list of (company_name, JobPosting) pairs.

    Silently skips ``<item>`` elements that are missing the required title
    or link, logging at DEBUG level.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        logger.warning("wwr: XML parse error for {url}: {exc}", url=feed_url, exc=exc)
        return []

    results: list[tuple[str, JobPosting]] = []
    channel = root.find("channel")
    if channel is None:
        logger.warning("wwr: no <channel> element in feed {url}", url=feed_url)
        return []

    for item in channel.findall("item"):
        title_el = item.find("title")
        link_el = item.find("link")

        raw_title: str | None = title_el.text if title_el is not None else None
        raw_link: str | None = link_el.text if link_el is not None else None

        if not raw_title or not raw_link:
            logger.debug(
                "wwr: skipping item with missing title or link in {url}",
                url=feed_url,
            )
            continue

        # Try the <wwr:region> custom tag for location; fall back to None.
        region_el = item.find(f"{{{_WWR_NS}}}region")
        location: str | None = (
            region_el.text.strip() if region_el is not None and region_el.text else None
        )

        company_name, job_title = _parse_title(raw_title)

        job = JobPosting(
            job_title=job_title,
            job_url=raw_link.strip(),
            location=location,
            remote_type="remote",   # WWR is remote-focused by definition
            source="wwr",
        )
        results.append((company_name, job))

    return results


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def discover(limit: int = 50) -> list[Company]:
    """Discover remote hiring companies from We Work Remotely RSS feeds.

    Iterates through :data:`_FEED_URLS`, fetches each feed, and maps
    ``<item>`` elements to :class:`~app.models.JobPosting` objects grouped
    by company name.  Collection stops once *limit* total job postings have
    been gathered.

    Note:
        Like :mod:`app.discover.remoteok`, this function takes a job-count
        *limit* rather than a slug list — it is a feed-style source.
        The number of :class:`~app.models.Company` objects returned is
        always ≤ *limit* (usually much fewer, since each company has
        multiple postings).

    Args:
        limit: Maximum total job postings to collect across all feeds.

    Returns:
        List of :class:`~app.models.Company` objects with at least one job.
    """
    by_company: dict[str, list[JobPosting]] = defaultdict(list)
    collected = 0
    rate_limiter = RateLimiter()

    with get_http_client() as client:
        for feed_url in _FEED_URLS:
            if collected >= limit:
                break

            logger.info("wwr: fetching feed {url}", url=feed_url)

            # Rate-limit between feed fetches (all hits to the same domain).
            rate_limiter.wait(feed_url)

            try:
                response = _fetch_with_retry(client, feed_url)
            except httpx.HTTPStatusError as exc:
                logger.warning(
                    "wwr: HTTP {status} for {url} — skipping feed",
                    status=exc.response.status_code,
                    url=feed_url,
                )
                continue
            except (httpx.TimeoutException, httpx.ConnectError, RetryError) as exc:
                logger.warning(
                    "wwr: network error after retries for {url} — {exc}",
                    url=feed_url,
                    exc=exc,
                )
                continue
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "wwr: unexpected error fetching {url} — {exc}",
                    url=feed_url,
                    exc=exc,
                )
                continue

            pairs = _parse_feed(response.text, feed_url)
            logger.info(
                "wwr: {n} item(s) parsed from {url}",
                n=len(pairs),
                url=feed_url,
            )

            for company_name, job in pairs:
                if collected >= limit:
                    break
                by_company[company_name].append(job)
                collected += 1

    logger.info(
        "wwr: collected {jobs} job(s) across {cos} company/companies (limit={limit})",
        jobs=collected,
        cos=len(by_company),
        limit=limit,
    )

    now = datetime.now()
    return [
        Company(
            name=name,
            ats_platform=None,   # WWR is a job board, not an ATS
            ats_slug=None,
            jobs=jobs,
            discovered_at=now,
            last_updated=now,
        )
        for name, jobs in by_company.items()
    ]

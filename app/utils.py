"""Shared HTTP utilities for hiring-radar.

All discover/scraper modules import from here — nothing in this file knows
about any specific ATS or job board.
"""

from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlparse

import httpx
from loguru import logger

from app.config import settings

# ---------------------------------------------------------------------------
# 1. HTTP client factory
# ---------------------------------------------------------------------------

def get_http_client() -> httpx.Client:
    """Return a pre-configured httpx.Client.

    Use as a context manager so connections are properly closed:

        with get_http_client() as client:
            resp = client.get("https://example.com")

    Settings applied:
    - ``User-Agent`` header from :data:`app.config.settings`
    - 10-second connect + read timeout
    - Redirects followed automatically
    """
    return httpx.Client(
        headers={"User-Agent": settings.user_agent},
        timeout=httpx.Timeout(10.0),
        follow_redirects=True,
    )


# ---------------------------------------------------------------------------
# 2. Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Per-domain rate limiter based on a minimum inter-request delay.

    Tracks the last-seen request timestamp per hostname and sleeps when
    necessary so that no two requests to the same host are closer together
    than ``settings.request_delay_seconds``.

    Dead simple — no token bucket, no async, single-threaded use only.
    """

    def __init__(self) -> None:
        self._last_request: dict[str, float] = {}

    def wait(self, url: str) -> None:
        """Block until it is safe to make a request to *url*'s host.

        Args:
            url: The full URL of the request about to be made.
        """
        hostname = urlparse(url).hostname or url
        delay = settings.request_delay_seconds
        now = time.monotonic()
        last = self._last_request.get(hostname)

        if last is not None:
            elapsed = now - last
            if elapsed < delay:
                sleep_for = delay - elapsed
                logger.debug(
                    "Rate-limiting {hostname}: sleeping {sleep_for:.2f}s",
                    hostname=hostname,
                    sleep_for=sleep_for,
                )
                time.sleep(sleep_for)

        self._last_request[hostname] = time.monotonic()


# ---------------------------------------------------------------------------
# 3. robots.txt checker
# ---------------------------------------------------------------------------

def is_allowed_by_robots(url: str, client: httpx.Client) -> bool:
    """Return ``True`` if our user-agent is permitted to fetch *url*.

    Fetches ``{scheme}://{netloc}/robots.txt``, parses it with
    :mod:`urllib.robotparser`, and checks the given path.

    On any error (network failure, missing file, parse error) this
    defaults to ``True`` — a missing or unreadable robots.txt is not
    treated as a blanket ban.  A debug-level log entry is emitted so the
    caller can trace permissiveness decisions.

    Note:
        Only needed before scraping arbitrary company *career pages*.
        Structured ATS JSON APIs (Greenhouse, Lever, Ashby …) are designed
        for programmatic consumption and do not need this check.
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        response = client.get(robots_url)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.debug(
            "robots.txt returned HTTP {status} for {robots_url} — allowing",
            status=exc.response.status_code,
            robots_url=robots_url,
        )
        return True
    except httpx.RequestError as exc:
        logger.debug(
            "Could not fetch robots.txt for {robots_url}: {exc} — allowing",
            robots_url=robots_url,
            exc=exc,
        )
        return True

    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.parse(response.text.splitlines())
    except Exception as exc:  # noqa: BLE001
        logger.debug(
            "Failed to parse robots.txt at {robots_url}: {exc} — allowing",
            robots_url=robots_url,
            exc=exc,
        )
        return True

    allowed = rp.can_fetch(settings.user_agent, url)
    if not allowed:
        logger.debug(
            "robots.txt disallows {user_agent} on {url}",
            user_agent=settings.user_agent,
            url=url,
        )
    return allowed


# ---------------------------------------------------------------------------
# 4. Safe GET wrapper
# ---------------------------------------------------------------------------

def safe_get(
    client: httpx.Client,
    url: str,
    rate_limiter: RateLimiter,
) -> httpx.Response | None:
    """Perform a rate-limited GET and return the response, or ``None`` on error.

    Steps:
    1. Calls :meth:`RateLimiter.wait` to honour per-domain throttling.
    2. Issues ``client.get(url)``.
    3. On any :exc:`httpx.HTTPError` logs a WARNING and returns ``None``
       instead of raising, so callers can handle missing pages gracefully.

    Args:
        client: A configured :func:`get_http_client` instance.
        url: The URL to fetch.
        rate_limiter: Shared :class:`RateLimiter` instance for the current
            scrape session.

    Returns:
        The :class:`httpx.Response` on success, ``None`` on any HTTP or
        network error.
    """
    rate_limiter.wait(url)
    try:
        response = client.get(url)
        response.raise_for_status()
        return response
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "HTTP {status} for {url}: {reason}",
            status=exc.response.status_code,
            url=url,
            reason=exc.response.reason_phrase,
        )
        return None
    except httpx.RequestError as exc:
        logger.warning(
            "Request error fetching {url}: {exc}",
            url=url,
            exc=exc,
        )
        return None

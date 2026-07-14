"""Best-effort career-page scraper for a single Company.

Career pages are heterogeneous by design — some are SPAs, some use custom
ATS widgets, and many gate useful content behind JavaScript.  This module
does what can be done with a plain synchronous HTTP GET + HTML parse, and
documents what it found (or failed to find) via ``company.notes``.

All parsing is wrapped so that a bad page never crashes the caller's loop.
The returned Company is always the same object passed in, mutated in-place
and returned for chaining.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import urljoin, urlparse

import httpx
from loguru import logger
from selectolax.parser import HTMLParser

from app.models import Company
from app.utils import RateLimiter, is_allowed_by_robots, safe_get

# ---------------------------------------------------------------------------
# Social-link patterns (order matters for matching priority)
# ---------------------------------------------------------------------------

_SOCIAL_DOMAINS: tuple[str, ...] = (
    "twitter.com",
    "x.com",
    "instagram.com",
    "facebook.com",
)
_LINKEDIN_PATTERN = re.compile(r"linkedin\.com/company/", re.IGNORECASE)
# Match github.com/<org-or-user> but not noise like /issues, /pulls, /blob, etc.
_GITHUB_PROFILE = re.compile(
    r"https?://github\.com/([A-Za-z0-9_\-]+)/?$", re.IGNORECASE
)

_MIN_USEFUL_TEXT_LEN = 200   # chars; below this we flag "minimal content"
_MAX_SOCIAL_LINKS = 5


# ---------------------------------------------------------------------------
# Public entry-point
# ---------------------------------------------------------------------------

def scrape_company_page(
    company: Company,
    client: httpx.Client,
    rate_limiter: RateLimiter,
) -> tuple[Company, str | None]:
    """Fetch and parse a company's career/web page, enriching *company* in place.

    This is a best-effort operation:

    - Tries ``career_page_url`` → ``website`` → ``https://{domain}`` in order.
    - Checks ``robots.txt`` before fetching any arbitrary company website.
    - Extracts description, LinkedIn, GitHub, and other social links from
      static HTML only — no JavaScript rendering.
    - Records every skip/failure as an appended note on ``company.notes``
      rather than raising an exception.

    Args:
        company: The :class:`~app.models.Company` to enrich.
        client: A configured :func:`~app.utils.get_http_client` instance.
        rate_limiter: Shared :class:`~app.utils.RateLimiter` for the session.

    Returns:
        A 2-tuple of ``(company, page_text)``:

        - *company* is the same object passed in, mutated and with
          ``last_updated`` refreshed.
        - *page_text* is the raw HTML string of the fetched page, or
          ``None`` when the page was skipped or the request failed.  Pass
          this directly to :func:`~app.scraper.contacts.extract_contacts`
          to avoid a second HTTP round-trip.
    """
    # ------------------------------------------------------------------
    # 1. Determine URL
    # ------------------------------------------------------------------
    url: str | None = (
        company.career_page_url
        or company.website
        or (f"https://{company.domain}" if company.domain else None)
    )

    if not url:
        _note(company, "scrape_skipped: no URL available")
        logger.debug("{name}: no URL to scrape", name=company.name)
        return company, None

    logger.info("scraping {name} → {url}", name=company.name, url=url)

    # ------------------------------------------------------------------
    # 2. robots.txt check
    # ------------------------------------------------------------------
    try:
        allowed = is_allowed_by_robots(url, client)
    except Exception as exc:  # noqa: BLE001
        logger.debug("{name}: robots check failed ({exc}) — allowing", name=company.name, exc=exc)
        allowed = True

    if not allowed:
        _note(company, "scrape_skipped: disallowed by robots.txt")
        logger.info("{name}: skipped (robots.txt)", name=company.name)
        return company, None

    # ------------------------------------------------------------------
    # 3. Fetch
    # ------------------------------------------------------------------
    response = safe_get(client, url, rate_limiter)
    if response is None:
        _note(company, "scrape_failed: request error")
        return company, None

    # ------------------------------------------------------------------
    # 4. Parse
    # ------------------------------------------------------------------
    try:
        _parse_and_enrich(company, response.text, url)
    except Exception as exc:  # noqa: BLE001
        _note(company, f"scrape_failed: parse error — {exc}")
        logger.warning("{name}: parse error — {exc}", name=company.name, exc=exc)
        # Still return the text so extract_contacts can try email extraction.

    # ------------------------------------------------------------------
    # 5. Refresh timestamp
    # ------------------------------------------------------------------
    company.last_updated = datetime.now()
    return company, response.text


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _note(company: Company, message: str) -> None:
    """Append *message* to ``company.notes`` (dedup guard included)."""
    if message not in company.notes:
        company.notes.append(message)


def _parse_and_enrich(company: Company, html: str, base_url: str) -> None:
    """Parse *html* and update *company* fields in place.

    All mutations are guarded: existing non-None values are never overwritten.
    """
    tree = HTMLParser(html)

    # Minimal-content guard
    body_text = tree.body.text(separator=" ").strip() if tree.body else ""
    if len(body_text) < _MIN_USEFUL_TEXT_LEN:
        _note(company, "scrape_partial: minimal content found")
        logger.debug(
            "{name}: minimal content ({n} chars)",
            name=company.name,
            n=len(body_text),
        )

    # --- Description candidates ---
    if company.description is None:
        # Prefer <meta name="description"> over <title>
        meta_desc = _meta_content(tree, "description")
        if meta_desc:
            company.description = meta_desc
        else:
            title_node = tree.css_first("title")
            if title_node and title_node.text(strip=True):
                company.description = title_node.text(strip=True)

    # --- Collect hrefs from <link> and <a> tags ---
    hrefs: list[str] = []
    for node in tree.css("a[href], link[href]"):
        raw = node.attributes.get("href", "") or ""
        raw = raw.strip()
        if not raw or raw.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        # Resolve relative URLs
        try:
            full = urljoin(base_url, raw)
        except Exception:  # noqa: BLE001
            continue
        hrefs.append(full)

    # --- LinkedIn ---
    if company.linkedin_url is None:
        for href in hrefs:
            if _LINKEDIN_PATTERN.search(href):
                company.linkedin_url = href
                logger.debug("{name}: found LinkedIn → {url}", name=company.name, url=href)
                break

    # --- GitHub ---
    if company.github_url is None:
        for href in hrefs:
            if _GITHUB_PROFILE.match(href):
                company.github_url = href
                logger.debug("{name}: found GitHub → {url}", name=company.name, url=href)
                break

    # --- Other social links ---
    existing_social = set(company.social_links)
    for href in hrefs:
        if len(company.social_links) >= _MAX_SOCIAL_LINKS:
            break
        parsed = urlparse(href)
        netloc = parsed.netloc.lower().lstrip("www.")
        if any(netloc.startswith(domain) for domain in _SOCIAL_DOMAINS):
            if href not in existing_social:
                company.social_links.append(href)
                existing_social.add(href)
                logger.debug("{name}: found social → {url}", name=company.name, url=href)


def _meta_content(tree: HTMLParser, name: str) -> str | None:
    """Return the ``content`` attribute of ``<meta name="{name}">``, or None."""
    node = tree.css_first(f'meta[name="{name}"]')
    if node is None:
        # Also try property= variant (Open Graph uses this)
        node = tree.css_first(f'meta[property="{name}"]')
    if node:
        content = (node.attributes.get("content") or "").strip()
        return content or None
    return None

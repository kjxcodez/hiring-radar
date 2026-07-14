"""Contact and email extraction from scraped page text.

This module operates on *text* already fetched by ``app.scraper.company``
— it never makes HTTP requests.  All extraction is regex-based and
heuristic; results should be treated as leads for manual verification,
not ground truth.

Two public functions are exposed:

- :func:`extract_contacts` — runs email extraction and classification on
  raw page text, mutating a :class:`~app.models.Company` in place.
- :func:`generate_common_email_guesses` — returns plausible cold-email
  guesses for a domain when no emails were actually found on the page.
  Guesses are **not** added to ``company.generic_emails``; they go into
  ``company.notes`` so it's always clear which addresses were scraped
  versus synthesised.
"""

from __future__ import annotations

import re
from collections import Counter

from loguru import logger

from app.models import Company

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Standard liberal email pattern — catches most real addresses with minimal
# false negatives.  False positives are pruned by _NOISE_DOMAINS below.
_EMAIL_RE = re.compile(r"[\w.+\-]+@[\w\-]+\.[\w.\-]+", re.IGNORECASE)

# Domains that routinely appear in page source but are analytics/error-
# tracking noise, not real company contact addresses.
# Extend this list freely; keep it sorted for readability.
_NOISE_DOMAINS: frozenset[str] = frozenset(
    {
        "example.com",
        "sentry.io",
        "wixpress.com",
        "google-analytics.com",
        "googletagmanager.com",
        "hotjar.com",
        "intercom.io",
        "segment.io",
        "segment.com",
        "amplitude.com",
        "mixpanel.com",
        "hubspot.com",
        "mailchimp.com",
        "sendgrid.net",
        "cloudflare.com",
        "jsdelivr.net",
        "unpkg.com",
        "githubusercontent.com",
    }
)

# Image-file-like false positives: things like "icon@2x.png" appear as emails
# when the regex runs on raw HTML source.  Filter them out by extension.
_NOISE_EXTENSIONS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp"}
)

# Local-part prefixes that classify an email as a generic/department address
# rather than a personal/recruiter address.
_GENERIC_PREFIXES: frozenset[str] = frozenset(
    {
        "hello",
        "careers",
        "jobs",
        "hr",
        "contact",
        "info",
        "recruiting",
        "recruitment",
        "talent",
        "apply",
        "hire",
        "team",
        "people",
    }
)

# Prefixes used for cold-outreach email guesses when no emails are found.
_GUESS_PREFIXES: list[str] = ["hello", "careers", "jobs", "hr", "contact"]


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def extract_contacts(company: Company, page_text: str) -> Company:
    """Extract and classify email addresses from *page_text*, updating *company*.

    Steps:

    1. Find all email-like strings with :data:`_EMAIL_RE`.
    2. Filter out noise (image extensions, known analytics domains).
    3. Classify each email:
       - Generic/department prefix → ``company.generic_emails`` (deduped).
       - Otherwise → ``company.recruiter_email`` if not already set.
         (Heuristic only — local-part of email does not guarantee it belongs
         to a recruiter; manual verification is always needed.)
    4. If ``company.domain`` is unset, infer it from the most-common email
       domain found in the text.
    5. If no emails were found *and* ``company.domain`` is available, append
       guessed email addresses to ``company.notes`` as a ``guessed_emails:``
       entry for manual reference.

    Args:
        company: The :class:`~app.models.Company` to enrich (mutated in place).
        page_text: Raw HTML or plain text already fetched from the company page.

    Returns:
        The same *company* object.
    """
    # --- 1. Find all raw email candidates ---
    raw_candidates: list[str] = _EMAIL_RE.findall(page_text)

    # --- 2. Filter noise ---
    clean: list[str] = []
    for email in raw_candidates:
        lower = email.lower()
        local, _, domain_part = lower.partition("@")
        # Drop image-extension false positives (e.g. "icon@2x.png")
        if any(domain_part.endswith(ext) for ext in _NOISE_EXTENSIONS):
            continue
        # Drop known analytics / infrastructure domains
        if domain_part in _NOISE_DOMAINS:
            continue
        # Drop clearly malformed addresses (no dot in domain)
        if "." not in domain_part:
            continue
        clean.append(email.lower())

    clean = list(dict.fromkeys(clean))  # preserve order, deduplicate
    logger.debug(
        "{name}: {total} email candidate(s) found, {kept} after filtering",
        name=company.name,
        total=len(raw_candidates),
        kept=len(clean),
    )

    # --- 3. Classify ---
    existing_generic = set(company.generic_emails)

    for email in clean:
        local_part = email.split("@")[0]
        if local_part in _GENERIC_PREFIXES:
            if email not in existing_generic:
                company.generic_emails.append(email)
                existing_generic.add(email)
                logger.debug("{name}: generic email → {email}", name=company.name, email=email)
        else:
            # Best-effort personal/recruiter candidate.
            # NOTE: This is a heuristic — the local part being non-generic
            # does not verify this is a recruiter.  Set only the first find.
            if company.recruiter_email is None:
                company.recruiter_email = email
                logger.debug("{name}: recruiter email candidate → {email}", name=company.name, email=email)

    # --- 4. Infer domain from most-common email domain ---
    if company.domain is None and clean:
        domain_counter: Counter[str] = Counter(
            email.split("@")[1] for email in clean
        )
        inferred_domain = domain_counter.most_common(1)[0][0]
        company.domain = inferred_domain
        logger.info(
            "{name}: inferred domain '{domain}' from email addresses",
            name=company.name,
            domain=inferred_domain,
        )

    # --- 5. Guessed emails when nothing was found ---
    if not clean:
        domain_for_guess = company.domain
        if domain_for_guess:
            guesses = generate_common_email_guesses(domain_for_guess)
            guess_note = "guessed_emails: " + ", ".join(guesses)
            # Only append once (re-runs should not duplicate the note)
            if not any(n.startswith("guessed_emails:") for n in company.notes):
                company.notes.append(guess_note)
                logger.debug(
                    "{name}: no emails found — recorded guesses in notes",
                    name=company.name,
                )
        else:
            logger.debug(
                "{name}: no emails found and no domain available — nothing to guess",
                name=company.name,
            )

    return company


def generate_common_email_guesses(domain: str) -> list[str]:
    """Return a list of plausible cold-outreach email addresses for *domain*.

    These are *not* scraped — they are pattern-based guesses using the most
    common department prefixes for tech companies.  Callers should treat them
    as starting points for manual outreach rather than verified addresses.

    Args:
        domain: The company's domain, e.g. ``"acmecorp.com"``.

    Returns:
        A list of email strings, e.g. ``["hello@acmecorp.com", "careers@acmecorp.com", ...]``.

    Example::

        >>> generate_common_email_guesses("acmecorp.com")
        ['hello@acmecorp.com', 'careers@acmecorp.com', 'jobs@acmecorp.com',
         'hr@acmecorp.com', 'contact@acmecorp.com']
    """
    return [f"{prefix}@{domain}" for prefix in _GUESS_PREFIXES]

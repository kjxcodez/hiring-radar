from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Callable, Any
from loguru import logger

from app.models import Company
from app.repositories import CompanyRepository
from app.scraper.company import scrape_company_page
from app.scraper.contacts import extract_contacts
from app.utils import RateLimiter, get_http_client
from app.config import Settings
from app.ai import AiGateway

class ScrapingService:
    def __init__(self, company_repo: CompanyRepository, settings: Settings, ai_gateway: AiGateway | None = None):
        self.company_repo = company_repo
        self.settings = settings
        self.ai_gateway = ai_gateway

    def scrape(
        self,
        company_filter: Optional[str] = None,
        force: bool = False,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> dict[str, int]:
        """Fetch career-page details and extract contact hints for each company in the database."""
        all_companies = self.company_repo.load_all()

        # Filter targets
        targets = all_companies
        if company_filter:
            targets = [c for c in all_companies if company_filter.lower() in c.name.lower()]
            if not targets:
                return {"processed": 0, "skipped": 0, "new_emails": 0, "failures": 0}

        n_processed = 0
        n_skipped = 0
        n_new_emails = 0
        n_failures = 0
        stale_threshold = timedelta(days=7)

        rate_limiter = RateLimiter()

        with get_http_client() as client:
            total_targets = len(targets)
            for idx, co in enumerate(targets):
                if progress_callback:
                    progress_callback(co.name, idx, total_targets)

                # Skip logic (unless --force)
                if not force:
                    has_contacts = bool(co.generic_emails or co.recruiter_email)
                    recently_scraped = (
                        (datetime.now() - co.last_updated) < stale_threshold
                    )
                    if has_contacts and recently_scraped:
                        n_skipped += 1
                        logger.debug(
                            "{name}: skipped (has contacts, scraped within 7 days)",
                            name=co.name,
                        )
                        continue

                try:
                    emails_before = len(co.generic_emails) + (1 if co.recruiter_email else 0)

                    # Scrape and extract
                    co, page_text = scrape_company_page(co, client, rate_limiter)
                    if page_text is not None:
                        extract_contacts(co, page_text)

                    emails_after = len(co.generic_emails) + (1 if co.recruiter_email else 0)
                    if emails_after > emails_before:
                        n_new_emails += 1

                    n_processed += 1

                    # Check for failures inside notes
                    if any(n.startswith("scrape_failed") for n in co.notes):
                        n_failures += 1

                except Exception as exc:  # noqa: BLE001
                    n_failures += 1
                    n_processed += 1
                    co.notes.append(f"scrape_failed: unexpected error — {exc}")
                    logger.warning("{name}: unexpected error — {exc}", name=co.name, exc=exc)

        # Merge updated targets back into full list
        updated_map = {c.dedupe_key(): c for c in targets}
        final = [updated_map.get(c.dedupe_key(), c) for c in all_companies]

        self.company_repo.save_all(final)

        return {
            "processed": n_processed,
            "skipped": n_skipped,
            "new_emails": n_new_emails,
            "failures": n_failures,
        }

    def enrich(
        self,
        model: Optional[str] = None,
        dry_run: bool = False,
        force: bool = False,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> dict[str, Any]:
        """Generate AI summaries and talking points for each company via an LLM."""
        all_companies = self.company_repo.load_all()

        targets = []
        skipped_count = 0
        for company in all_companies:
            if force or not company.ai_summary:
                targets.append(company)
            else:
                skipped_count += 1

        if not targets:
            return {
                "targets": [],
                "n_enriched": 0,
                "n_failures": 0,
                "skipped_count": skipped_count,
            }

        n_enriched = 0
        n_failures = 0

        rate_limiter = RateLimiter()
        from app.enrich import enrich as _enrich_ai

        total_targets = len(targets)
        for idx, co in enumerate(targets):
            if progress_callback:
                progress_callback(co.name, idx, total_targets)

            if not dry_run:
                rate_limiter.wait("https://openrouter.ai")

            try:
                _enrich_ai(co, model=model, dry_run=dry_run, ai_gateway=self.ai_gateway)
                if any(n.startswith("enrich_failed") for n in co.notes):
                    n_failures += 1
                else:
                    n_enriched += 1
            except Exception as exc:  # noqa: BLE001
                n_failures += 1
                co.notes.append(f"enrich_failed: unexpected error — {exc}")
                logger.warning("enrich/{name}: unexpected error — {exc}", name=co.name, exc=exc)

        if not dry_run:
            # Re-merge updated targets with skipped ones
            updated_map = {c.dedupe_key(): c for c in targets}
            final = [updated_map.get(c.dedupe_key(), c) for c in all_companies]
            self.company_repo.save_all(final)

        return {
            "targets": targets,
            "n_enriched": n_enriched,
            "n_failures": n_failures,
            "skipped_count": skipped_count,
        }

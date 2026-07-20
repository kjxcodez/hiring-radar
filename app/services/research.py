from __future__ import annotations

from typing import Optional
from app.models import Company
from app.repositories import CompanyRepository
from app.enrich.research import research_company
from app.utils import RateLimiter, get_http_client
from app.config import Settings


class ResearchService:
    """Service to perform deep AI/Github research on a company."""

    def __init__(self, company_repo: CompanyRepository, settings: Settings):
        self.company_repo = company_repo
        self.settings = settings

    def research(
        self,
        company_name: str,
        model: Optional[str] = None,
        dry_run: bool = False,
    ) -> Company:
        """Fetch Github profile details and call OpenRouter to perform deeper intelligence queries."""
        # Retrieve the company using the common repository lookup logic
        co = self.company_repo.find_by_name(company_name)

        rate_limiter = RateLimiter()
        with get_http_client() as client:
            co = research_company(co, client, rate_limiter, model=model, dry_run=dry_run)

        if not dry_run:
            all_companies = self.company_repo.load_all()
            # Re-merge and save
            for idx, item in enumerate(all_companies):
                if item.dedupe_key() == co.dedupe_key():
                    all_companies[idx] = co
                    break
            self.company_repo.save_all(all_companies)

        return co

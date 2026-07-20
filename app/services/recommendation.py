from __future__ import annotations

import re
from datetime import datetime, date
from typing import Optional, Any

from app.models import Company
from app.repositories import CompanyRepository, ProfileRepository
from app.resume.parser import load_resume_text
from app.config import Settings

class RecommendationService:
    def __init__(self, company_repo: CompanyRepository, profile_repo: ProfileRepository, settings: Settings):
        self.company_repo = company_repo
        self.profile_repo = profile_repo
        self.settings = settings

    def get_recommendations(self, top: int = 5, resume_label: Optional[str] = None) -> list[dict[str, Any]]:
        """Rank and return recommendations based on overall company desirability and resume overlap."""
        all_companies = self.company_repo.load_all()

        # Exclude contacted companies (notes containing email_sent:)
        uncontacted = [
            c for c in all_companies
            if not any(n.startswith("email_sent:") for n in c.notes)
        ]

        # Load resume if label/path resolves
        resume_text = None
        resume_path = None
        if resume_label or self.settings.resume_path:
            # Import resolve_resume_path lazily to avoid circular dependencies
            from app.cli import resolve_resume_path
            try:
                resume_path = resolve_resume_path(resume_label)
                if resume_path and resume_path.exists():
                    resume_text = load_resume_text(resume_path)
            except Exception:
                pass

        def get_recency(co: Company) -> datetime:
            dates = [
                datetime.combine(j.posted_date, datetime.min.time())
                for j in co.jobs if j.posted_date
            ]
            if dates:
                return max(dates)
            return co.discovered_at or datetime.min

        def calculate_heuristic_fit(co: Company, r_text: str) -> int:
            r_words = set(re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", r_text.lower()))
            if not r_words:
                return 0
            co_text = (
                (co.description or "")
                + " "
                + " ".join(j.job_title + " " + (j.description or "") for j in co.jobs)
            )
            co_words = set(re.findall(r"\b[a-zA-Z0-9_\-\.]{3,}\b", co_text.lower()))
            return len(r_words.intersection(co_words))

        scored_list = []
        unscored_list = []

        for co in uncontacted:
            is_scored = co.company_score_overall is not None
            recency = get_recency(co)
            fit_score = 0
            if resume_text:
                fit_score = calculate_heuristic_fit(co, resume_text)

            item = {
                "company": co,
                "is_scored": is_scored,
                "overall": co.company_score_overall,
                "recency": recency,
                "fit_score": fit_score,
            }
            if is_scored:
                scored_list.append(item)
            else:
                unscored_list.append(item)

        scored_list.sort(key=lambda x: (x["overall"], x["recency"]), reverse=True)
        unscored_list.sort(key=lambda x: x["recency"], reverse=True)

        ranked = scored_list + unscored_list
        top_items = ranked[:top]

        result = []
        for item in top_items:
            co = item["company"]
            result.append({
                "company": co,
                "is_scored": item["is_scored"],
                "overall": item["overall"],
                "recency": item["recency"],
                "fit_score": item["fit_score"],
                "resume_path": resume_path,
            })
        return result

from __future__ import annotations

from pathlib import Path
from typing import Optional, Any
from datetime import datetime

from app.models import Company
from app.repositories import CompanyRepository, ProfileRepository
from app.resume.parser import load_resume_text
from app.resume.score import score_company
from app.resume.suggestions import suggest_resume_tailoring
from app.resume.versions import resolve_resume_version, list_resume_versions
from app.config import Settings


class ResumeService:
    """Service to score resumes and generate tailored resumes/suggestions."""

    def __init__(self, company_repo: CompanyRepository, profile_repo: ProfileRepository, settings: Settings):
        self.company_repo = company_repo
        self.profile_repo = profile_repo
        self.settings = settings

    def list_versions(self) -> list[str]:
        """Return a sorted list of all available resume stems in the resumes/ folder."""
        return list_resume_versions()

    def resolve_version_path(self, label: Optional[str]) -> Optional[Path]:
        """Find the file Path matching the provided version label, or default from settings."""
        if not label:
            return self.settings.resume_path

        p = Path(label)
        if p.exists() and p.is_file():
            return p

        return resolve_resume_version(label)

    def parse_resume(self, resume_path: Path) -> str:
        """Load text content from the resume (TXT or PDF)."""
        return load_resume_text(resume_path)

    def score_compatibility(
        self,
        company_name: str,
        resume_label: Optional[str] = None,
        model: Optional[str] = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Compare resume text against jobs to determine match ratings, missing skills, and metrics."""
        co = self.company_repo.find_by_name(company_name)

        resume_path = self.resolve_version_path(resume_label)
        if not resume_path:
            raise ValueError("Resume path is not set in settings or passed options.")

        resume_text = self.parse_resume(resume_path)

        result = score_company(co, resume_text, model=model, dry_run=dry_run)
        return {
            "company": co,
            "resume_path": resume_path,
            "overall_match_percent": result.get("overall_match_percent", 0),
            "skill_breakdown": result.get("skill_breakdown", {}),
            "missing_skills": result.get("missing_skills", []),
        }

    def suggest_tailoring(
        self,
        company_name: str,
        resume_label: Optional[str] = None,
        model: Optional[str] = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Generate keywords, projects, objective highlights, and reordering suggestions for tailoring."""
        co = self.company_repo.find_by_name(company_name)

        resume_path = self.resolve_version_path(resume_label)
        if not resume_path:
            raise ValueError("Resume path is not set in settings or passed options.")

        resume_text = self.parse_resume(resume_path)

        suggestions = suggest_resume_tailoring(co, resume_text, model=model, dry_run=dry_run)

        if not dry_run:
            from datetime import date
            note_text = f"tailoring_suggested: {date.today().isoformat()}"
            if note_text not in co.notes:
                co.notes.append(note_text)
            co.last_updated = datetime.now()

            all_companies = self.company_repo.load_all()
            for idx, item in enumerate(all_companies):
                if item.dedupe_key() == co.dedupe_key():
                    all_companies[idx] = co
                    break
            self.company_repo.save_all(all_companies)

        return {
            "company": co,
            "resume_path": resume_path,
            "suggestions": suggestions,
        }

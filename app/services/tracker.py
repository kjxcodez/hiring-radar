from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from app.models import Application, ApplicationStatus, Company
from app.repositories import ApplicationRepository, CompanyRepository
from app.tracker.status import set_status

class TrackerService:
    def __init__(self, application_repo: ApplicationRepository, company_repo: CompanyRepository):
        self.application_repo = application_repo
        self.company_repo = company_repo

    def get_applications(self) -> dict[str, Application]:
        """Load all tracking records from applications.json."""
        return self.application_repo.load_all()

    def update_status(
        self,
        company_name: str,
        status: ApplicationStatus,
        resume_version: Optional[str] = None,
    ) -> dict[str, Any]:
        """Transition status workflow for a company, saving changes and validating transition sequence."""
        all_companies = self.company_repo.load_all()

        matches = [c for c in all_companies if company_name.lower() in c.name.lower()]
        if not matches:
            raise ValueError(f"Company '{company_name}' not found.")
        if len(matches) > 1:
            raise ValueError(f"Multiple companies match '{company_name}': " + ", ".join(c.name for c in matches))

        co = matches[0]
        key = co.dedupe_key()

        apps = self.application_repo.load_all()
        old_app = apps.get(key)
        old_status = old_app.status if old_app else "none"

        app_record = set_status(apps, key, status)
        if resume_version:
            app_record.resume_version = resume_version

        self.application_repo.save_all(apps)

        return {
            "company": co,
            "company_key": key,
            "old_status": old_status,
            "new_status": status,
            "resume_version": resume_version,
            "app_record": app_record,
        }

    def add_note(self, company_name: str, note_text: str) -> Application:
        """Append a note log to the application tracking record."""
        all_companies = self.company_repo.load_all()

        matches = [c for c in all_companies if company_name.lower() in c.name.lower()]
        if not matches:
            raise ValueError(f"Company '{company_name}' not found.")
        if len(matches) > 1:
            raise ValueError(f"Multiple companies match '{company_name}': " + ", ".join(c.name for c in matches))

        co = matches[0]
        key = co.dedupe_key()

        apps = self.application_repo.load_all()
        if key not in apps:
            app_record = Application(
                company_key=key,
                status="discovered",
                status_history=[{"status": "discovered", "date": date.today().isoformat()}],
            )
            apps[key] = app_record
        else:
            app_record = apps[key]

        note_entry = f"{date.today().isoformat()}: {note_text}"
        app_record.notes.append(note_entry)

        self.application_repo.save_all(apps)
        return app_record

    def get_notes(self, company_name: str) -> list[str]:
        """List all tracking notes recorded for a company's application."""
        all_companies = self.company_repo.load_all()

        matches = [c for c in all_companies if company_name.lower() in c.name.lower()]
        if not matches:
            raise ValueError(f"Company '{company_name}' not found.")
        if len(matches) > 1:
            raise ValueError(f"Multiple companies match '{company_name}': " + ", ".join(c.name for c in matches))

        co = matches[0]
        key = co.dedupe_key()

        apps = self.application_repo.load_all()
        app_record = apps.get(key)
        if not app_record:
            return []
        return app_record.notes

    def get_followups(self, threshold_days: int = 7) -> list[dict[str, Any]]:
        """Surface application tracking records needing follow-up based on contact dates."""
        all_companies = self.company_repo.load_all()
        co_map = {c.dedupe_key(): c.name for c in all_companies}

        apps = self.application_repo.load_all()
        today = date.today()
        candidates = []

        for key, app in apps.items():
            if app.status not in ("applied", "interviewing"):
                continue
            if not app.last_contact_date:
                continue

            days_since = (today - app.last_contact_date).days
            if days_since >= threshold_days:
                candidates.append({
                    "key": key,
                    "name": co_map.get(key, key),
                    "status": app.status,
                    "days_since": days_since,
                    "applied_date": app.applied_date,
                })

        candidates.sort(key=lambda x: x["days_since"], reverse=True)
        return candidates

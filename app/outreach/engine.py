"""Outreach and CRM Engine managing application preparation and outreach drafts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional
from loguru import logger

from app.models import Application
from app.outreach.profile import OutreachMessage
from app.outreach.cover_letter import CoverLetterGenerator
from app.outreach.email import generate_email
from app.outreach.linkedin import LinkedInMessageGenerator
from app.outreach.referral import ReferralRequestGenerator
from app.outreach.scheduler import FollowUpScheduler
from app.outreach.timeline import TimelineTracker
from app.resume.suggestions import suggest_resume_tailoring
from app.recommendation.profile import CandidateProfile

if TYPE_CHECKING:
    from app.services.config import ServiceContainer


class OutreachEngine:
    """Coordinates cover letter, email, LinkedIn, and referral request drafting."""

    def __init__(self, container: ServiceContainer):
        self.container = container

    def prepare_application(
        self,
        company_name: str,
        candidate: Optional[CandidateProfile] = None,
        force: bool = False,
    ) -> Application:
        """Execute the CRM preparation pipeline for a target company."""
        # 1. Load company and job opening
        company = self.container.company_repo.find_by_name(company_name)
        if not company:
            raise ValueError(f"Company '{company_name}' not found in database.")

        job = None
        if company.jobs:
            # Prefer most recent job posting
            job = sorted(
                company.jobs,
                key=lambda j: j.posted_date.isoformat() if j.posted_date else "",
                reverse=True,
            )[0]
        else:
            from app.models import JobPosting
            job = JobPosting(
                job_title="Software Engineer",
                job_url=f"https://{company.domain or 'example.com'}/careers",
                source="manual",
            )

        # 2. Resolve Candidate Profile
        if not candidate:
            profile_cache = self.container.settings.output_dir / "candidate_profile.json"
            if profile_cache.exists():
                data = self.container.storage.read(profile_cache)
                candidate = CandidateProfile.model_validate(data)
            else:
                candidate = CandidateProfile()

        # 3. Check if application already prepared
        app_repo = self.container.application_repo
        apps = app_repo.load_all()
        co_key = company.dedupe_key()

        if co_key in apps and not force:
            logger.info(f"Application for '{company.name}' already prepared in CRM.")
            return apps[co_key]

        # 4. Tailor Resume Suggestions
        resume_text = self._build_resume_text(candidate)
        tailoring_suggestions = {}
        try:
            tailoring_suggestions = suggest_resume_tailoring(
                company=company,
                resume_text=resume_text,
                ai_gateway=self.container.ai_gateway,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Resume tailoring suggestions failed for {company.name}: {exc}")

        # Save tailored resume notes to application notes
        notes = []
        if tailoring_suggestions:
            notes.append(f"Tailoring suggestions: {tailoring_suggestions}")

        # 5. Generate Cover Letter
        cover_letter = CoverLetterGenerator.generate(
            candidate=candidate,
            job=job,
            company=company,
            gateway=self.container.ai_gateway,
        )

        # 6. Generate Email Outreach
        email_draft = {}
        try:
            email_draft = generate_email(
                company=company,
                ai_gateway=self.container.ai_gateway,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Email drafting failed for {company.name}: {exc}")

        # 7. Generate LinkedIn Recruiter Message
        linkedin_draft = LinkedInMessageGenerator.generate(
            candidate=candidate,
            job=job,
            company=company,
            gateway=self.container.ai_gateway,
        )

        # 8. Generate Referral Request Message
        referral_draft = ReferralRequestGenerator.generate(
            candidate=candidate,
            job=job,
            company=company,
            gateway=self.container.ai_gateway,
        )

        # 9. Build follow-up schedule
        schedule = FollowUpScheduler.create_schedule()

        # 10. Construct outreach messages list
        messages = []
        now_str = datetime.utcnow().isoformat()
        if email_draft:
            messages.append(
                OutreachMessage(
                    channel="email",
                    subject=email_draft.get("subject", ""),
                    content=email_draft.get("body", ""),
                    generated_at=now_str,
                )
            )
        if linkedin_draft:
            messages.append(
                OutreachMessage(
                    channel="linkedin",
                    content=linkedin_draft.get("content", ""),
                    generated_at=now_str,
                )
            )
        if referral_draft:
            messages.append(
                OutreachMessage(
                    channel="referral",
                    content=referral_draft.get("content", ""),
                    generated_at=now_str,
                )
            )

        # 11. Create and populate Application record
        app = Application(
            company_key=co_key,
            status="Prepared",
            candidate=candidate,
            company=company,
            job=job,
            cover_letter_version=cover_letter.get("full_letter", ""),
            messages=messages,
            followup_schedule=schedule,
            next_followup="Day 0: Submit application on career portal",
            notes=notes,
            last_updated=datetime.utcnow(),
        )

        # 12. Log initial timeline event
        TimelineTracker.log_event(
            application=app,
            event="Application created",
            description=f"Outreach drafts prepared and follow-up schedule initialized for {company.name}.",
        )

        # 13. Persist
        apps[co_key] = app
        app_repo.save_all(apps)
        logger.info(f"Successfully prepared outreach for '{company.name}' and saved to CRM.")

        return app

    def _build_resume_text(self, candidate: CandidateProfile) -> str:
        parts = []
        if candidate.skills:
            parts.append(f"Skills: {', '.join(candidate.skills)}")
        if candidate.technologies:
            parts.append(f"Technologies: {', '.join(candidate.technologies)}")
        if candidate.years_experience:
            parts.append(f"Experience: {candidate.years_experience} years")
        return "\n".join(parts)

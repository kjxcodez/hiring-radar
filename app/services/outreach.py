from __future__ import annotations

from typing import Optional, Any
from datetime import datetime, date

from app.models import Company
from app.repositories import CompanyRepository
from app.outreach.email import generate_email
from app.outreach.mailer import send_email, send_test_email
from app.config import Settings, YamlConfig
from app.exceptions import CompanyNotFoundError


class OutreachService:
    """Service to handle generating, marking, and sending outreach emails."""

    def __init__(self, company_repo: CompanyRepository, settings: Settings, yaml_config: YamlConfig):
        self.company_repo = company_repo
        self.settings = settings
        self.yaml_config = yaml_config

    def generate_outreach_draft(
        self,
        company_name: str,
        template: str = "startup",
        model: Optional[str] = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Generate email subject line and body candidates for a company."""
        co = self.company_repo.find_by_name(company_name)
        res = generate_email(co, template_name=template, model=model, dry_run=dry_run)
        recipient = co.recruiter_email or (co.generic_emails[0] if co.generic_emails else "(no email found)")

        return {
            "company": co,
            "recipient": recipient,
            "subject": res.get("subject", ""),
            "body": res.get("body", ""),
            "template_used": res.get("template_used", template),
        }

    def send_outreach_email(self, recipient: str, subject: str, body: str) -> bool:
        """Deliver plain-text outreach email to the destination using settings credentials."""
        return send_email(to_address=recipient, subject=subject, body=body)

    def send_test_email(self, to_address: str) -> bool:
        """Deliver connection verification email."""
        return send_test_email(to_address=to_address)

    def mark_email_sent(self, company_name: str, template: str) -> None:
        """Append email_sent metadata note to the company record and refresh timestamp."""
        try:
            co = self.company_repo.find_by_name(company_name)
        except CompanyNotFoundError:
            return

        note_text = f"email_sent: {date.today().isoformat()} via {template}"
        if note_text not in co.notes:
            co.notes.append(note_text)
        co.last_updated = datetime.now()

        all_companies = self.company_repo.load_all()
        for idx, item in enumerate(all_companies):
            if item.dedupe_key() == co.dedupe_key():
                all_companies[idx] = co
                break
        self.company_repo.save_all(all_companies)

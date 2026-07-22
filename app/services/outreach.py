from __future__ import annotations

from typing import Optional, Any
from datetime import datetime, date

from app.repositories import CompanyRepository
from app.config import Settings, YamlConfig
from app.exceptions import CompanyNotFoundError
from app.ai import AiGateway


class OutreachService:
    """Service to handle generating, marking, and sending outreach emails."""

    def __init__(
        self,
        company_repo: CompanyRepository,
        settings: Settings,
        yaml_config: YamlConfig,
        ai_gateway: AiGateway | None = None,
        workflow_engine: Any = None,
    ):
        self.company_repo = company_repo
        self.settings = settings
        self.yaml_config = yaml_config
        self.ai_gateway = ai_gateway
        self._workflow_engine = workflow_engine

    @property
    def workflow_engine(self) -> Any:
        """Resolve WorkflowEngine instance from CLI container context."""
        if self._workflow_engine is None:
            from app.cli.common import get_container
            self._workflow_engine = get_container().workflow_engine
        return self._workflow_engine

    def generate_outreach_draft(
        self,
        company_name: str,
        template: str = "startup",
        model: Optional[str] = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Generate email subject line and body candidates for a company."""
        from app.workflows.context import WorkflowContext

        context = WorkflowContext(
            settings=self.settings,
            container=self.workflow_engine.container,
        )

        res = self.workflow_engine.run(
            "outreach",
            context=context,
            company_name=company_name,
            template=template,
            model=model,
            dry_run=dry_run,
        )
        return res

    def send_outreach_email(self, recipient: str, subject: str, body: str) -> bool:
        """Deliver plain-text outreach email to the destination using settings credentials."""
        from app.outreach.mailer import send_email
        return send_email(to_address=recipient, subject=subject, body=body)

    def send_test_email(self, to_address: str) -> bool:
        """Deliver connection verification email."""
        from app.outreach.mailer import send_test_email
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

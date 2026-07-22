"""Unit tests for the extended Application CRM models."""

from __future__ import annotations

from datetime import datetime
from app.models import Application
from app.outreach.profile import OutreachMessage, Recruiter, Referral, FollowUp, TimelineEntry


def test_application_crm_models():
    msg = OutreachMessage(channel="linkedin", content="Hi Recruiter", generated_at="2026-07-23T00:00:00")
    rec = Recruiter(name="Alice", email="alice@stripe.com", role="Tech Recruiter")
    ref = Referral(name="Bob", connection="Alumni", status="contacted")
    fup = FollowUp(day=5, action="Follow-up", template_name="followup_1")
    tline = TimelineEntry(event="Applied", description="Submitted application", timestamp="2026-07-23T01:00:00")

    app = Application(
        company_key="stripe.com",
        status="Prepared",
        recruiter=rec,
        referral=ref,
        messages=[msg],
        timeline=[tline],
        followup_schedule=[fup],
        last_updated=datetime.utcnow(),
    )

    assert app.company_key == "stripe.com"
    assert app.status == "Prepared"
    assert app.recruiter.name == "Alice"
    assert app.referral.name == "Bob"
    assert app.messages[0].channel == "linkedin"
    assert app.timeline[0].event == "Applied"
    assert app.followup_schedule[0].day == 5

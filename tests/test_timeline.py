"""Unit tests for the CRM TimelineTracker appending events."""

from __future__ import annotations

from app.models import Application
from app.outreach.timeline import TimelineTracker


def test_timeline_tracker():
    app = Application(
        company_key="stripe.com",
        status="Prepared",
    )

    assert len(app.timeline) == 0

    TimelineTracker.log_event(app, "Screening Scheduled", "First video interview setup.")
    assert len(app.timeline) == 1
    assert app.timeline[0].event == "Screening Scheduled"
    assert app.timeline[0].description == "First video interview setup."
    assert app.timeline[0].timestamp is not None

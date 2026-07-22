"""Unit tests for independent change detectors."""

from __future__ import annotations

from app.models import JobPosting, Application
from app.monitoring.detectors import (
    JobChangeDetector,
    IntelligenceChangeDetector,
    ApplicationChangeDetector,
)


def test_job_change_detector():
    j1 = JobPosting(job_title="Developer", job_url="http://co.com/1", remote_type="hybrid", source="greenhouse")
    j2 = JobPosting(job_title="Developer", job_url="http://co.com/1", remote_type="remote", source="greenhouse")

    events = JobChangeDetector.detect("Stripe", [j1], [j2])
    assert len(events) == 1
    assert events[0].event_type == "RemotePolicyChanged"


def test_intelligence_change_detector():
    old = {"tech_stack": ["Go"]}
    new = {"tech_stack": ["Go", "Rust"]}

    events = IntelligenceChangeDetector.detect("Stripe", old, new)
    assert len(events) == 1
    assert events[0].event_type == "EngineeringStackChanged"


def test_application_change_detector():
    app1 = Application(company_key="stripe.com", status="Prepared")
    app2 = Application(company_key="stripe.com", status="Applied")

    events = ApplicationChangeDetector.detect({"stripe.com": app1}, {"stripe.com": app2})
    assert len(events) == 1
    assert events[0].event_type == "ApplicationStatusChanged"
    assert events[0].previous_value == "Prepared"
    assert events[0].current_value == "Applied"
